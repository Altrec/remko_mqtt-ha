import logging
import json
import asyncio
import time
from collections.abc import Callable, Coroutine
from datetime import timedelta

import attr

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.components.input_number import (
    ATTR_VALUE as INP_ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_RELOAD as NUMBER_SERVICE_RELOAD,
    SERVICE_SET_VALUE as NUMBER_SERVICE_SET_VALUE,
)
from homeassistant.components.input_select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_RELOAD as SELECT_SERVICE_RELOAD,
    SERVICE_SELECT_OPTION as SELECT_SERVICE_SET_OPTION,
)
from homeassistant.components.input_boolean import (
    DOMAIN as BOOLEAN_DOMAIN,
    SERVICE_RELOAD as BOOLEAN_SERVICE_RELOAD,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_OPTION,
)
from homeassistant.components import mqtt
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    DOMAIN,
    CONF_ID,
    CONF_MQTT_NODE,
    CONF_MQTT_DBG,
    CONF_LANGUAGE,
    CONF_FREQ,
    AVAILABLE_LANGUAGES,
)
from .remko_regs import (
    FIELD_MAXVALUE,
    FIELD_MINVALUE,
    FIELD_REGNUM,
    FIELD_REGTYPE,
    FIELD_UNIT,
    id_names,
    reg_id,
)

_LOGGER = logging.getLogger(__name__)


class HeatPump:
    _dbg = True
    _mqtt_base = ""
    _langid = 0
    _unsub_data: Callable[[], None] | None = None
    _unsub_cmd: Callable[[], None] | None = None
    _watchdog_unsub: Callable[[], None] | None = None

    # ###
    async def message_received(self, message):
        """Handle new MQTT messages."""
        _LOGGER.debug(
            "%s: message.payload:[%s] [%s]", self._id, message.topic, message.payload
        )
        try:
            # In case the heatpump is controlled from another client don't send query_list
            if "CLIENT2HOST" in message.topic:
                if "CLIENT_ID" in message.payload:
                    self._last_time = time.time()
                    _LOGGER.debug("Message from other client")
            elif self._mqtt_counter == self._freq:
                json_dict = json.loads(message.payload)
                json_dict = json_dict.get("values")
                if message.topic == self._data_topic:
                    for k in json_dict:
                        # Map incomming registers to named settings based on id_reg (Remko_regs)
                        if k in self._id_reg:
                            _LOGGER.debug("[%s] [%s] [%s]", self._id, k, json_dict[k])

                            # Internal mapping of Remko_MQTT regs, used to create update events
                            self._hpstate[k] = json_dict[k]
                            if reg_id[self._id_reg[k]][1] == "switch":
                                self._hpstate[k] = int(self._hpstate[k], 16) > 0
                            if reg_id[self._id_reg[k]][1] == "sensor_el":
                                self._hpstate[k] = int(self._hpstate[k], 16) * 100
                            if reg_id[self._id_reg[k]][1] == "sensor_en":
                                self._hpstate[k] = int(self._hpstate[k], 16)
                            if reg_id[self._id_reg[k]][1] == "sensor_counter":
                                self._hpstate[k] = int(self._hpstate[k], 16)
                            if reg_id[self._id_reg[k]][1] in [
                                "sensor_temp",
                                "sensor_temp_inp",
                            ]:
                                raw = int(self._hpstate[k], 16)
                                self._hpstate[k] = (
                                    -(raw & 0x8000) | (raw & 0x7FFF)
                                ) / 10
                            if reg_id[self._id_reg[k]][1] == "sensor_mode":
                                mode = f"opmode{int(json_dict[k], 16)}"
                                self._hpstate[k] = id_names[mode][self._langid]
                            if reg_id[self._id_reg[k]][1] == "select_input":
                                if self._id_reg[k] == "main_mode":
                                    mode = f"mode{int(json_dict[k], 16)}"
                                elif self._id_reg[k] == "dhw_opmode":
                                    mode = f"dhwopmode{int(json_dict[k], 16)}"
                                self._hpstate[k] = id_names[mode][self._langid]

                    self._hpstate["communication_status"] = json_dict.get(
                        "vp_read", "Ok"
                    )

                    self._hass.bus.fire(
                        self._domain + "_" + self._id + "_msg_rec_event", {}
                    )

                    await self.mqtt_keep_alive()
                    self._mqtt_counter = 0

                else:
                    _LOGGER.error("JSON result was not from Remko-mqtt")
            else:
                self._mqtt_counter += 1
        except ValueError:
            _LOGGER.error("MQTT payload could not be parsed as JSON")
            _LOGGER.debug("Erroneous JSON: %s", message.payload)

    def __init__(self, hass, entry: ConfigEntry):
        self._hass = hass
        self._entry = entry
        self._hpstate = {}
        self._domain = DOMAIN
        self._id = entry.data[CONF_ID]
        self._id_reg = {}
        self._capabilites = []
        # store individual unsubscribe callbacks
        self._unsub_data = None
        self._unsub_cmd = None
        self._freq = entry.data[CONF_FREQ]
        self._last_time = time.time()
        self._mqtt_counter = entry.data[CONF_FREQ]

        # Create reverse lookup dictionary (id_reg->reg_number)
        for k, v in reg_id.items():
            self._id_reg[v[0]] = k
            self._hpstate[v[0]] = -1

    async def check_capabilities(self):
        # Check capabilites/possible reg_ids
        value = "true"
        query_list = "[" + ",".join(str(i) for i in range(1001, 5999)) + "]"
        payload = json.dumps({"FORCE_RESPONSE": value, "query_list": query_list})
        await mqtt.async_publish(
            self._hass,
            self._cmd_topic,
            payload=payload,
            qos=2,
            retain=False,
        )

        # Wait for the reply
        future = asyncio.Future()

        @callback
        def message_received(msg):
            future.set_result(msg.payload)

        unsub = await mqtt.async_subscribe(
            self._hass, self._data_topic, message_received
        )

        try:
            reply = await future
        finally:
            unsub()

        json_dict = json.loads(reply)
        json_dict = json_dict.get("values")

        for k in json_dict:
            self._capabilites.append(k)

    async def setup_mqtt(self):
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

        # Schedule watchdog using Home Assistant helpers (registers an unsubscribe)
        self._hass.async_create_task(self.watchdog())

        # """ Wait before getting new values """
        await asyncio.sleep(5)
        self._mqtt_counter = self._freq
        self._hass.bus.fire(self._domain + "_" + self._id + "_msg_rec_event", {})

    async def remove_mqtt(self):
        # Call stored unsubscribe callbacks
        if self._unsub_data is not None:
            try:
                self._unsub_data()
            finally:
                self._unsub_data = None

        if self._unsub_cmd is not None:
            try:
                self._unsub_cmd()
            finally:
                self._unsub_cmd = None

        # Unregister watchdog if active
        if self._watchdog_unsub is not None:
            try:
                self._watchdog_unsub()
            finally:
                self._watchdog_unsub = None

    async def update_config(self, entry):
        # Unsubscribe any existing subscriptions before updating topics
        if self._unsub_data is not None:
            self._unsub_data()
            self._unsub_data = None
        if self._unsub_cmd is not None:
            self._unsub_cmd()
            self._unsub_cmd = None
        # Unregister watchdog while updating
        if self._watchdog_unsub is not None:
            self._watchdog_unsub()
            self._watchdog_unsub = None
        lang = entry.data[CONF_LANGUAGE]
        self._langid = AVAILABLE_LANGUAGES.index(lang)
        self._dbg = entry.data[CONF_MQTT_DBG]
        self._mqtt_base = entry.data[CONF_MQTT_NODE] + "/SMTID/"
        self._data_topic = self._mqtt_base + "HOST2CLIENT"
        self._cmd_topic = self._mqtt_base + "CLIENT2HOST"
        self._freq = entry.data[CONF_FREQ]

        # Provide some debug info
        _LOGGER.debug(
            f"INFO: {self._domain}_{self._id} mqtt_node: [{entry.data[CONF_MQTT_NODE]}]"
        )

        if self._dbg is True:
            self._mqtt_base = self._mqtt_base + "dbg_"
            _LOGGER.error("INFO: MQTT Debug write enabled")

        _LOGGER.debug("Language[%s]", self._langid)

        await self.mqtt_keep_alive()

    async def async_reset(self):
        """Reset this heatpump to default state."""
        # unsubscribe here
        return True

    @property
    def hpstate(self):
        return self._hpstate

    def get_value(self, item):
        """Get value for sensor."""
        res = self._hpstate.get(item)
        _LOGGER.debug("get_value(" + item + ")=%d", res)
        return res

    def update_state(self, command, state_command):
        """Send MQTT message to Remko."""
        _LOGGER.debug("update_state:" + command + " " + state_command)

    async def send_mqtt_reg(self, register_id, value) -> None:
        """Service to send a message."""

        register = reg_id[register_id][0]
        reg_type = reg_id[register_id][1]
        _LOGGER.debug("register:[%s]", register)

        if not isinstance(value, (int, float)) or value is None:
            _LOGGER.error("No MQTT message sent due to missing value:[%s]", value)
            return

        if register not in self._id_reg:
            _LOGGER.error("No MQTT message sent due to unknown register:[%s]", register)
            return

        if reg_type == "sensor_temp_inp":
            topic = self._cmd_topic
            hex_str = hex(int(value * 10)).upper()
            hex_str = hex_str[2:].zfill(4)
            payload = json.dumps({"values": {register: hex_str}})
        elif reg_type == "select_input":
            topic = self._cmd_topic
            if register_id == "main_mode":
                value = value + 1
            value = str(value).zfill(2)
            payload = json.dumps({"values": {register: value}})
        elif reg_type in ("switch", "action"):
            topic = self._cmd_topic
            hex_str = hex(int(value))
            hex_str = hex_str[2:].zfill(2)
            payload = json.dumps({"values": {register: hex_str}})

        _LOGGER.debug("topic:[%s]", topic)
        _LOGGER.debug("payload:[%s]", payload)
        self._hass.async_create_task(
            mqtt.async_publish(self._hass, topic, payload, qos=2, retain=False)
        )
        """ Wait before getting new values """
        await asyncio.sleep(5)
        self._mqtt_counter = self._freq
        self._hass.bus.fire(self._domain + "_" + self._id + "_msg_rec_event", {})

    async def mqtt_keep_alive(self) -> None:
        """Heatpump sends MQTT messages only when triggered."""

        topic = self._cmd_topic
        value = "true"
        if reg_id:
            query_list = (
                "[" + ",".join(entry[FIELD_REGNUM] for entry in reg_id.values()) + "]"
            )
        else:
            query_list = "[]"
        payload = json.dumps({"FORCE_RESPONSE": value, "query_list": query_list})

        _LOGGER.debug("topic:[%s]", topic)
        _LOGGER.debug("payload:[%s]", payload)
        self._hass.async_create_task(
            mqtt.async_publish(self._hass, topic, payload, qos=2, retain=False)
        )

    async def watchdog(self) -> None:
        """Register a periodic checker that triggers mqtt_keep_alive when no messages arrive."""
        from homeassistant.core import callback

        @callback
        def _check(now):
            if time.time() - self._last_time >= 300:  # 5 minutes
                _LOGGER.debug(
                    "No MQTT message received for 5 minutes, calling mqtt_keep_alive"
                )
                # schedule the coroutine
                self._hass.async_create_task(self.mqtt_keep_alive())

        # Register a once-per-minute checker and keep the unsubscribe callable
        self._watchdog_unsub = async_track_time_interval(
            self._hass, _check, timedelta(minutes=1)
        )
