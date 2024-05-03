import logging
from typing import TYPE_CHECKING, Literal, final
from homeassistant.core import HomeAssistant, callback


from homeassistant.components.button import ButtonEntity
from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    EntityCategory,
)

from homeassistant.helpers.device_registry import DeviceEntryType

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

if TYPE_CHECKING:
    from functools import cached_property
else:
    from homeassistant.backports.functools import cached_property

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
        """Add a Remko button property"""
        async_add_entities([sensor], True)
        # _LOGGER.debug('Added new sensor %s / %s', sensor.entity_id, sensor.unique_id)

    worker = hass.data[DOMAIN].worker
    heatpump = hass.data[DOMAIN]._heatpumps[config_entry.data[CONF_ID]]
    entities = []

    for key in reg_id:
        if reg_id[key][FIELD_REGTYPE] == "action":
            device_id = key
            if key in id_names:
                friendly_name = id_names[key][heatpump._langid]
            else:
                friendly_name = None
            vp_reg = reg_id[key][FIELD_REGNUM]

            entities.append(
                HeatPumpButton(
                    hass,
                    heatpump,
                    device_id,
                    vp_reg,
                    friendly_name,
                )
            )
    async_add_entities(entities)


class HeatPumpButton(ButtonEntity):
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
        if device_id == "dhw_heating":
            self._icon = "mdi:heat-wave"
        else:
            self._icon = "mdi:lightning-outline"

        self._entity_picture = None
        self._available = True

        self._idx = device_id
        self._vp_reg = vp_reg

        self._attr_device_info = {
            ATTR_IDENTIFIERS: {(heatpump._id, "Remko-MQTT")},
            ATTR_NAME: CONF_NAME,
            ATTR_MANUFACTURER: "Remko",
            ATTR_MODEL: CONF_VER,
            "entry_type": DeviceEntryType.SERVICE,
        }

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
        return self._state

    @property
    def vp_reg(self):
        """Return the device class of the sensor."""
        return self._vp_reg

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
        return f"{DOMAIN}_HeatPumpButton"

    async def async_press(self) -> None:
        value = int(0)
        await self.heatpump.send_mqtt_reg(self.reg_id, value)
