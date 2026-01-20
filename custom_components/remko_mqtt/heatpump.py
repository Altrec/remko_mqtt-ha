import logging
import json
import asyncio
import time
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.components import mqtt
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    DOMAIN,
    CONF_ID,
    CONF_MQTT_NODE,
    CONF_LANGUAGE,
    CONF_FREQ,
    AVAILABLE_LANGUAGES,
)
from .remko_regs import remko_reg_translation, remko_reg
from .timeprogram_converter import RemkoTimeProgramConverter

_LOGGER = logging.getLogger(__name__)

# Constants
_KEEP_ALIVE_INTERVAL = 30  # seconds
_WATCHDOG_TIMEOUT = 300  # 5 minutes
_WATCHDOG_CHECK_INTERVAL = timedelta(minutes=1)
_MQTT_SLEEP_DURATION = 5  # seconds


class HeatPump:
    """MQTT interface for Remko heat pump systems."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize heat pump instance."""
        # Core HomeAssistant references
        self._hass = hass
        self._entry = entry

        # Device identification
        self._domain = DOMAIN
        self._id = entry.data[CONF_ID]

        # Configuration
        self._freq = entry.data[CONF_FREQ]

        # Language setup
        lang = entry.data[CONF_LANGUAGE]
        self._langid = AVAILABLE_LANGUAGES.index(lang)

        # MQTT configuration
        self._mqtt_base = entry.data[CONF_MQTT_NODE] + "/SMTID/"
        self._data_topic = self._mqtt_base + "HOST2CLIENT"
        self._cmd_topic = self._mqtt_base + "CLIENT2HOST"

        # Device state and register mapping
        self._reg_name = {}
        self._hpstate = {}
        self._reg_time = {}
        self._build_reverse_lookup()

        # Device capabilities
        self._capabilities = []

        # MQTT subscriptions
        self._unsub_data: Callable[[], None] | None = None
        self._unsub_cmd: Callable[[], None] | None = None
        self._watchdog_unsub: Callable[[], None] | None = None

        # Timing and counters
        self._last_time = time.time()
        self._keep_alive_delay = time.time() - _KEEP_ALIVE_INTERVAL
        self._mqtt_counter = entry.data[CONF_FREQ]

    def _build_reverse_lookup(self) -> None:
        """Build reverse lookup dictionary for register mapping."""
        for name, data in remko_reg.items():
            self._reg_name[data[0]] = name
            self._hpstate[data[0]] = "unknown"

    async def message_received(self, message) -> None:
        """Handle new MQTT messages."""
        _LOGGER.debug("[%s] MQTT message received:  topic=%s", self._id, message.topic)
        try:
            # if self._mqtt_counter >= self._freq:
            #    await self._process_message(message)
            #    self._mqtt_counter = 0
            # else:
            #    self._mqtt_counter += 1
            await self._process_message(message)
        except ValueError:
            _LOGGER.error(
                "MQTT payload could not be parsed as JSON:  %s", message.payload
            )

    async def _process_message(self, message) -> None:
        """Process MQTT message by topic."""
        # Check for other clients controlling the heat pump
        if message.topic == self._cmd_topic:
            if "CLIENT_ID" in message.payload:
                _LOGGER.debug(
                    "Message from other client, delaying query_list for 30 seconds"
                )
                self._keep_alive_delay = time.time()
                return

        # Process data from heat pump
        if message.topic == self._data_topic:
            self._last_time = time.time()
            json_dict = json.loads(message.payload).get("values", {})

            for register_id, value in json_dict.items():
                if register_id in self._reg_name:
                    self._update_hpstate(register_id, value)

            self._hass.bus.fire(f"{self._domain}_{self._id}_msg_rec_event", {})
            await self.mqtt_keep_alive()

    def _update_hpstate(self, reg_id: str, value: str) -> None:
        """Update heat pump state with converted register value."""
        _LOGGER.debug("[%s] Register %s:  %s", self._id, reg_id, value)
        reg_type = remko_reg[self._reg_name[reg_id]][1]

        if reg_type == "switch":
            self._hpstate[reg_id] = int(value, 16) > 0
        elif reg_type == "timeprogram":
            self._hpstate[reg_id] = RemkoTimeProgramConverter.hex_to_timeprogram(value)
        elif reg_type == "sensor_el":
            if (
                reg_id not in self._reg_time
                or time.time() - self._reg_time[reg_id] > self._freq
            ):
                self._reg_time[reg_id] = time.time()
                self._hpstate[reg_id] = int(value, 16) * 100
        elif reg_type in ("sensor_en", "sensor_counter"):
            if (
                reg_id not in self._reg_time
                or time.time() - self._reg_time[reg_id] > self._freq
            ):
                self._reg_time[reg_id] = time.time()
                self._hpstate[reg_id] = int(value, 16)
        elif reg_type == "sensor_temp":
            if (
                reg_id not in self._reg_time
                or time.time() - self._reg_time[reg_id] > self._freq
            ):
                self._reg_time[reg_id] = time.time()
                raw = int(value, 16)
                self._hpstate[reg_id] = (-(raw & 0x8000) | (raw & 0x7FFF)) / 10
        elif reg_type == "sensor_temp_inp":
            raw = int(value, 16)
            self._hpstate[reg_id] = (-(raw & 0x8000) | (raw & 0x7FFF)) / 10
        elif reg_type == "sensor_mode":
            mode = f"opmode{int(value, 16)}"
            self._hpstate[reg_id] = remko_reg_translation[mode][self._langid]
        elif reg_type == "select_input":
            self._hpstate[reg_id] = self._get_select_mode(self._reg_name[reg_id], value)

    def _get_select_mode(self, reg_id: str, value: str) -> str:
        """Get select mode display name from register value."""
        int_value = int(value, 16)
        mode_map = {
            "main_mode": f"mode{int_value}",
            "dhw_opmode": f"dhwopmode{int_value}",
            "timemode": f"timemode{int_value}",
            "user_profile": f"user_profile{int_value}",
        }
        mode = mode_map.get(reg_id, f"mode{int_value}")
        return remko_reg_translation[mode][self._langid]

    async def check_capabilities(self) -> bool:
        """Check capabilities/possible register IDs from heat pump."""
        # Capablility check disbaled for now, since not all values are reported correctly
        self._capabilities = list(self._reg_name.keys())
        """
        query_list = [int(key) for key in self._reg_name]
        payload = json.dumps(
            {
                "FORCE_RESPONSE": True,
                "values": {"5074": "0255", "5106": "0000", "5109": "0000"},
                "query_list": query_list,
            }
        )
        await mqtt.async_publish(
            self._hass,
            self._cmd_topic,
            payload=payload,
            qos=2,
            retain=False,
        )

        future: asyncio.Future = asyncio.Future()

        @callback
        def message_handler(msg) -> None:
            #Handle capability response.
            if not future.done() and not future.cancelled():
                try:
                    future.set_result(msg.payload)
                except (asyncio.InvalidStateError, RuntimeError) as e:
                    _LOGGER.warning("Could not set future result (late message): %s", e)

        unsub = await mqtt.async_subscribe(
            self._hass, self._data_topic, message_handler
        )

        try:
            reply = await asyncio.wait_for(future, timeout=30.0)
            json_dict = json.loads(reply).get("values", {})
            self._capabilities = list(json_dict.keys())
            return True
        except TimeoutError:
            _LOGGER.error(
                "Timeout waiting for capabilities response from heat pump.  "
                "Check:  1) MQTT broker running, 2) Heat pump connected, 3) Correct MQTT node"
            )
            self._capabilities = list(self._reg_name.keys())
            return False
        except asyncio.CancelledError:
            _LOGGER.warning("Capability check was cancelled (likely during shutdown)")
            raise
        except Exception:
            _LOGGER.exception("Unexpected error during capability check")
            self._capabilities = list(self._reg_name.keys())
            return False
        finally:
            unsub()
        """
        return True

    async def setup_mqtt(self) -> None:
        """Initialize MQTT subscriptions and watchdog."""
        self._unsub_data = await mqtt.async_subscribe(
            self._hass,
            self._data_topic,
            self.message_received,
        )
        self._unsub_cmd = await mqtt.async_subscribe(
            self._hass,
            self._cmd_topic,
            self.message_received,
        )

        self._hass.async_create_task(self.watchdog())

        await asyncio.sleep(_MQTT_SLEEP_DURATION)
        self._mqtt_counter = self._freq
        self._hass.bus.fire(f"{self._domain}_{self._id}_msg_rec_event", {})

    async def remove_mqtt(self) -> None:
        """Remove all MQTT subscriptions."""
        unsubs = [self._unsub_data, self._unsub_cmd, self._watchdog_unsub]
        for unsub in unsubs:
            if unsub is not None:
                try:
                    unsub()
                except (RuntimeError, ValueError) as e:
                    _LOGGER.debug("Error unsubscribing: %s", e)

        self._unsub_data = None
        self._unsub_cmd = None
        self._watchdog_unsub = None

    async def update_config(self, entry: ConfigEntry) -> None:
        """Update configuration from config entry."""
        # Clean up existing subscriptions
        await self.remove_mqtt()

        # Update configuration
        lang = entry.data[CONF_LANGUAGE]
        self._langid = AVAILABLE_LANGUAGES.index(lang)
        self._mqtt_base = entry.data[CONF_MQTT_NODE] + "/SMTID/"
        self._data_topic = self._mqtt_base + "HOST2CLIENT"
        self._cmd_topic = self._mqtt_base + "CLIENT2HOST"
        self._freq = entry.data[CONF_FREQ]

        _LOGGER.debug(
            "Heat pump %s configured with MQTT node:  %s, language: %s",
            self._id,
            entry.data[CONF_MQTT_NODE],
            self._langid,
        )

        await self.mqtt_keep_alive()

    async def async_reset(self) -> bool:
        """Reset heat pump to default state."""
        return True

    @property
    def hpstate(self) -> dict:
        """Return current heat pump state."""
        return self._hpstate

    def get_value(self, item: str) -> Any:
        """Get value for sensor."""
        res = self._hpstate.get(item)
        _LOGGER.debug("get_value(%s)=%s", item, res)
        return res

    def update_state(self, command: str, state_command: str) -> None:
        """Send MQTT message to heat pump."""
        _LOGGER.debug("update_state:  %s %s", command, state_command)

    async def send_mqtt_reg(self, reg_name: str, value: Any) -> None:
        """Send register value to heat pump via MQTT."""
        if value is None:
            _LOGGER.error("Cannot send register - value is None:  %s", reg_name)
            return

        reg_id = remko_reg[reg_name][0]
        reg_type = remko_reg[reg_name][1]
        if reg_id not in self._reg_name:
            _LOGGER.error("Unknown register: %s", reg_id)
            return

        _LOGGER.debug("Sending register:  %s (type: %s)", reg_id, reg_type)

        payload = self._build_mqtt_payload(reg_id, reg_type, reg_name, value)

        _LOGGER.debug("MQTT topic: %s, payload: %s", self._cmd_topic, payload)

        self._hass.async_create_task(
            mqtt.async_publish(
                self._hass, self._cmd_topic, payload, qos=2, retain=False
            )
        )

        await asyncio.sleep(_MQTT_SLEEP_DURATION)
        self._mqtt_counter = self._freq
        self._hass.bus.fire(f"{self._domain}_{self._id}_msg_rec_event", {})

    def _build_mqtt_payload(
        self, reg_id: str, reg_type: str, reg_name: str, value: Any
    ) -> str:
        """Build MQTT payload based on reg_type."""
        if reg_type == "timeprogram":
            return json.dumps({"values": {reg_id: value}})
        if reg_type == "sensor_temp_inp":
            hex_str = hex(int(value * 10)).upper()[2:].zfill(4)
            return json.dumps({"values": {reg_id: hex_str}})

        if reg_type == "select_input":
            int_value = int(value) + (1 if reg_name == "main_mode" else 0)
            return json.dumps({"values": {reg_id: str(int_value).zfill(2)}})
        if reg_type in ("switch", "action"):
            hex_str = hex(int(value))[2:].zfill(2)
            return json.dumps({"values": {reg_id: hex_str}})

        return json.dumps({"values": {reg_id: value}})

    async def mqtt_keep_alive(self) -> None:
        """Send keep-alive message to heat pump."""
        if time.time() - self._keep_alive_delay < _KEEP_ALIVE_INTERVAL:
            return

        self._keep_alive_delay = time.time()
        query_list = (
            [int(cap) for cap in self._capabilities] if self._capabilities else []
        )

        payload = json.dumps(
            {
                "FORCE_RESPONSE": True,
                "values": {"5074": "0255", "5106": "0000", "5109": "0000"},
                "query_list": query_list,
            }
        )

        _LOGGER.debug("Sending keep-alive message to heat pump")

        self._hass.async_create_task(
            mqtt.async_publish(
                self._hass, self._cmd_topic, payload, qos=2, retain=False
            )
        )

    async def watchdog(self) -> None:
        """Monitor MQTT connection and trigger keep-alive when needed."""

        @callback
        def _check(now) -> None:
            """Check if keep-alive is needed."""
            if time.time() - self._last_time >= _WATCHDOG_TIMEOUT:
                _LOGGER.debug("No MQTT message for 5 minutes, triggering keep-alive")
                self._hass.async_create_task(self.mqtt_keep_alive())

        self._watchdog_unsub = async_track_time_interval(
            self._hass, _check, _WATCHDOG_CHECK_INTERVAL
        )
