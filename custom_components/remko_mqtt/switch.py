import logging
from typing import Literal, final
from homeassistant.core import HomeAssistant, callback
from functools import cached_property

from homeassistant.const import STATE_OFF, STATE_ON

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    STATE_OFF,
    STATE_ON,
    EntityCategory,
)

from homeassistant.helpers.device_registry import DeviceEntryType

from homeassistant.const import PERCENTAGE
from .const import (
    DOMAIN,
    CONF_ID,
    CONF_NAME,
    CONF_VER,
)

from .remko_regs import (
    FIELD_REGNUM,
    FIELD_REGTYPE,
    id_names,
    reg_id,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass, config_entry, async_add_entities, discovery_info=None
):
    """Set up platform for a new integration.
    Called by the HA framework after async_setup_platforms has been called
    during initialization of a new integration.
    """

    @callback
    def async_add_sensor(sensor):
        """Add a Remko sensor property"""
        async_add_entities([sensor], True)
        # _LOGGER.debug('Added new sensor %s / %s', sensor.entity_id, sensor.unique_id)

    worker = hass.data[DOMAIN].worker
    heatpump = hass.data[DOMAIN]._heatpumps[config_entry.data[CONF_ID]]
    entities = []

    for key in reg_id:
        if reg_id[key][FIELD_REGTYPE] == "switch":
            device_id = key
            if key in id_names:
                friendly_name = id_names[key][heatpump._langid]
            else:
                friendly_name = None
            vp_reg = reg_id[key][FIELD_REGNUM]

            entities.append(
                HeatPumpSwitch(
                    hass,
                    heatpump,
                    device_id,
                    vp_reg,
                    friendly_name,
                )
            )
    async_add_entities(entities)


class HeatPumpSwitch(SwitchEntity):
    """Common functionality for all entities."""

    def __init__(self, hass, heatpump, device_id, vp_reg, friendly_name):
        self.hass = hass
        self._heatpump = heatpump
        self._hpstate = heatpump._hpstate

        # set HA instance attributes directly (mostly don't use property)
        self._attr_unique_id = f"{heatpump._domain}_{device_id}"
        self.entity_id = f"switch.{heatpump._domain}_{device_id}"

        _LOGGER.debug("entity_id:" + self.entity_id)
        _LOGGER.debug("idx:" + device_id)
        self._name = friendly_name
        self._state = None
        if device_id == "absence_mode":
            self._icon = "mdi:plane-car"
        elif device_id == "party_mode":
            self._icon = "mdi:party-popper"
        else:
            self._icon = "mdi:gauge"

        self._entity_picture = None
        self._available = True

        self._idx = device_id
        self._vp_reg = vp_reg

        # Listen for the Remko rec event indicating new data
        hass.bus.async_listen(
            heatpump._domain + "_" + heatpump._id + "_msg_rec_event",
            self._async_update_event,
        )

        self._attr_device_info = {
            ATTR_IDENTIFIERS: {(heatpump._id, "Remko-MQTT")},
            ATTR_NAME: CONF_NAME,
            ATTR_MANUFACTURER: "Remko",
            ATTR_MODEL: CONF_VER,
            "entry_type": DeviceEntryType.SERVICE,
        }

    async def async_turn_on(self):
        value = int(1)
        await self._heatpump.send_mqtt_reg(self._idx, value)

    async def async_turn_off(self):
        value = int(0)
        await self._heatpump.send_mqtt_reg(self._idx, value)

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def should_poll(self):
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @final
    @property
    def state(self) -> Literal["on", "off"]:
        """Return the state of the sensor."""
        return STATE_ON if (self._state) else STATE_OFF

    @property
    def vp_reg(self):
        """Return the device class of the sensor."""
        return self._vp_reg

    @cached_property
    def is_on(self) -> bool:
        return self._state == True

    @property
    def sorter(self):
        """Return the state of the sensor."""
        return self._sorter

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._icon

    @property
    def device_class(self):
        """Return the class of this device."""
        return f"{DOMAIN}_HeatPumpSwitch"

    async def async_update(self):
        """Update the value of the entity."""
        """Update the new state of the sensor."""

        _LOGGER.debug("update: " + self._idx)
        reg_state = self._hpstate.get_value(self._vp_reg)
        if self._state is None:
            _LOGGER.warning("Could not get data for %s", self._idx)
        else:
            self._state = int(reg_state) > 0

    async def _async_update_event(self, event):
        """Update the new state of the sensor."""

        _LOGGER.debug("event: " + self._idx)
        reg_state = self._hpstate[self._vp_reg]
        if reg_state is None:
            _LOGGER.debug("Could not get data for %s", self._idx)
            self._state = None
            bool_state = None
        else:
            bool_state = int(reg_state) > 0

        if self._state != bool_state:
            self._state = bool_state
            self.async_schedule_update_ha_state()
            _LOGGER.debug("async_update_ha: %s", str(bool_state))
