"""Module for Remko MQTT binary sensor integration."""

import logging
from typing import Literal, final

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
)
from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType
from propcache import cached_property

from .const import (
    DOMAIN,
    CONF_ID,
    CONF_NAME,
    CONF_VER,
)

from .remko_regs import (
    FIELD_REGNUM,
    FIELD_REGTYPE,
    FIELD_UNIT,
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
        """Add a Remko binary sensor property"""
        async_add_entities([sensor], True)
        # _LOGGER.debug('Added new sensor %s / %s', sensor.entity_id, sensor.unique_id)

    worker = hass.data[DOMAIN].worker
    heatpump = hass.data[DOMAIN]._heatpumps[config_entry.data[CONF_ID]]
    entities = []

    for key in reg_id:
        if (
            reg_id[key][FIELD_REGTYPE] == "binary_sensor"
            and reg_id[key][FIELD_REGNUM] in heatpump._capabilites
        ):
            device_id = key
            if key in id_names:
                friendly_name = id_names[key][heatpump._langid]
            else:
                friendly_name = None
            vp_reg = reg_id[key][FIELD_REGNUM]
            vp_type = reg_id[key][FIELD_REGTYPE]
            vp_unit = reg_id[key][FIELD_UNIT]

            entities.append(
                HeatPumpBinarySensor(
                    hass,
                    heatpump,
                    device_id,
                    vp_reg,
                    friendly_name,
                    vp_type,
                    vp_unit,
                )
            )
    async_add_entities(entities)


class HeatPumpBinarySensor(BinarySensorEntity):
    """Common functionality for all entities."""

    def __init__(
        self, hass, heatpump, device_id, vp_reg, friendly_name, vp_type, vp_unit
    ):
        self.hass = hass
        self._heatpump = heatpump
        self._hpstate = heatpump._hpstate

        # set HA instance attributes directly (mostly don't use property)
        self._attr_unique_id = f"{heatpump._domain}_{device_id}"
        self.entity_id = f"binary_sensor.{heatpump._domain}_{device_id}"

        _LOGGER.debug("entity_id:" + self.entity_id)
        _LOGGER.debug("idx:" + device_id)
        self._name = friendly_name
        self._state = None
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

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def should_poll(self):
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @final
    @property
    def state(self) -> Literal["on", "off"]:
        """Return the state of the sensor."""
        return STATE_ON if (self._state == "01") else STATE_OFF

    @property
    def vp_reg(self):
        """Return the device class of the sensor."""
        return self._vp_reg

    @cached_property
    def is_on(self) -> bool:
        return self._state == True

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._icon

    async def async_update(self):
        """Update the value of the entity."""

        _LOGGER.debug("update: " + self._idx)
        self._state = self._hpstate.get_value(self._vp_reg)
        if self._state is None:
            _LOGGER.warning("Could not get data for %s", self._idx)

    async def _async_update_event(self, event):
        """Update the new state of the sensor."""

        _LOGGER.debug("event: " + self._idx)
        state = self._hpstate[self._vp_reg]
        if state is None:
            _LOGGER.debug("Could not get data for %s", self._idx)
        if self._state != state:
            self._state = state
            self.async_schedule_update_ha_state()
            _LOGGER.debug("async_update_ha: %s", str(state))

    @property
    def device_class(self):
        """Return the class of this device."""
        return f"{DOMAIN}_HeatPumpSensor"
