import logging
import json
import asyncio
import time
from collections.abc import Callable, Coroutine

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

from .const import (
    DOMAIN,
    CONF_ID,
    CONF_MQTT_NODE,
    CONF_MQTT_DBG,
    CONF_LANGUAGE,
    CONF_FREQ,
    CONF_TIMER,
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
    unsubscribe_callback: Callable[[], None]

    # ###
    @callback
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
                            if reg_id[self._id_reg[k]][1] in [
                                "temperature",
                                "temperature_input",
                            ]:
                                self._hpstate[k] = int(self._hpstate[k], 16) / 10
                            if reg_id[self._id_reg[k]][1] in [
                                "energy",
                            ]:
                                self._hpstate[k] = int(self._hpstate[k], 16)
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
        self.unsubscribe_callback = None
        self._freq = entry.data[CONF_FREQ]
        self._timer = entry.data[CONF_TIMER]
        self._last_time = time.time() - self._timer
        self._mqtt_counter = entry.data[CONF_FREQ]

        # Create reverse lookup dictionary (id_reg->reg_number)

        for k, v in reg_id.items():
            self._id_reg[v[0]] = k
            self._hpstate[v[0]] = -1

    async def check_capabilities(self):
        # Check capabilites/possible reg_ids
        value = "true"
        query_list = "["
        for i in range(1001, 5997):
            query_list += str(i) + ","
        query_list += "5998]"
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
        self.unsubscribe_callback = await mqtt.async_subscribe(
            self._hass,
            self._data_topic,
            self.message_received,
        )
        self.unsubscribe_callback = await mqtt.async_subscribe(
            self._hass,
            self._cmd_topic,
            self.message_received,
        )

        # Schedule the watchdog to run periodically
        self._hass.loop.create_task(self.watchdog())

        # """ Wait before getting new values """
        await asyncio.sleep(5)
        self._mqtt_counter = self._freq
        self._hass.bus.fire(self._domain + "_" + self._id + "_msg_rec_event", {})

    async def remove_mqtt(self):
        self.unsubscribe_callback = await mqtt.async_unload_entry(
            self._hass,
            self._data_topic,
            self.message_received,
        )
        self.unsubscribe_callback = await mqtt.async_unload_entry(
            self._hass,
            self._cmd_topic,
            self.message_received,
        )

    async def update_config(self, entry):
        if self.unsubscribe_callback is not None:
            self.unsubscribe_callback()
        lang = entry.data[CONF_LANGUAGE]
        self._langid = AVAILABLE_LANGUAGES.index(lang)
        self._dbg = entry.data[CONF_MQTT_DBG]
        self._mqtt_base = entry.data[CONF_MQTT_NODE] + "/SMTID/"
        self._data_topic = self._mqtt_base + "HOST2CLIENT"
        self._cmd_topic = self._mqtt_base + "CLIENT2HOST"
        self._freq = entry.data[CONF_FREQ]
        self._timer = entry.data[CONF_TIMER]

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

    # ### ##################################################################
    # Write specific value_id with data, value_id will be translated to register number.
    # Default service used by input_number automations

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

        if reg_type == "temperature_input":
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
        query_list = "["
        for key in reg_id:
            query_list += reg_id[key][FIELD_REGNUM] + ","
        query_list = query_list[:-1]
        query_list += "]"
        query_list and time.time() - self._last_time >= self._timer
        payload = json.dumps({"FORCE_RESPONSE": value, "query_list": query_list})

        _LOGGER.debug("topic:[%s]", topic)
        _LOGGER.debug("payload:[%s]", payload)
        self._hass.async_create_task(
            mqtt.async_publish(self._hass, topic, payload, qos=2, retain=False)
        )

    async def watchdog(self):
        """Check if no MQTT message has been received for 5 minutes and call mqtt_keep_alive."""
        while True:
            await asyncio.sleep(60)  # Check every minute
            if time.time() - self._last_time >= 300:  # 5 minutes
                _LOGGER.debug(
                    "No MQTT message received for 5 minutes, calling mqtt_keep_alive"
                )
                await self.mqtt_keep_alive()
