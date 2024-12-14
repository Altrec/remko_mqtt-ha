import logging
from homeassistant.core import callback

from homeassistant.components.number import NumberEntity
from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
)
from homeassistant.helpers.device_registry import DeviceEntryType

from homeassistant.const import UnitOfTemperature

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
    FIELD_MINVALUE,
    FIELD_MAXVALUE,
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

    worker = hass.data[DOMAIN].worker
    heatpump = hass.data[DOMAIN]._heatpumps[config_entry.data[CONF_ID]]
    entities = []

    for key in reg_id:
        if reg_id[key][FIELD_REGTYPE] == "temperature_input":
            device_id = key
            if key in id_names:
                friendly_name = id_names[key][heatpump._langid]
            else:
                friendly_name = None
            vp_reg = reg_id[key][FIELD_REGNUM]
            vp_type = reg_id[key][FIELD_REGTYPE]
            vp_unit = reg_id[key][FIELD_UNIT]
            vp_min = reg_id[key][FIELD_MINVALUE]
            vp_max = reg_id[key][FIELD_MAXVALUE]
            vp_step = 0.5
            vp_mode = "box"

            entities.append(
                HeatPumpNumber(
                    hass,
                    heatpump,
                    device_id,
                    vp_reg,
                    friendly_name,
                    vp_type,
                    vp_unit,
                    vp_min,
                    vp_max,
                    vp_step,
                    vp_mode,
                )
            )
    async_add_entities(entities)


class HeatPumpNumber(NumberEntity):
    """Common functionality for all entities."""

    def __init__(
        self,
        hass,
        heatpump,
        device_id,
        vp_reg,
        friendly_name,
        vp_type,
        vp_unit,
        vp_min,
        vp_max,
        vp_step,
        vp_mode,
    ):
        self.hass = hass
        self._heatpump = heatpump
        self._hpstate = heatpump._hpstate

        # set HA instance attributes directly (mostly don't use property)
        self._attr_unique_id = f"{heatpump._domain}_{device_id}"
        self.entity_id = f"number.{heatpump._domain}_{device_id}"

        _LOGGER.debug("entity_id:" + self.entity_id)
        _LOGGER.debug("idx:" + device_id)
        self._name = friendly_name
        self._state = None
        self._icon = None
        if (
            vp_type
            in [
                "temperature",
                "temperature_input",
            ]
        ) or (
            vp_unit
            in [
                "C",
            ]
        ):
            self._icon = "mdi:temperature-celsius"
            self._unit = UnitOfTemperature.CELSIUS
        else:
            if vp_unit:
                self._unit = vp_unit
            else:
                self._unit = None
            self._icon = "mdi:gauge"
        # "mdi:thermometer" ,"mdi:oil-temperature", "mdi:gauge", "mdi:speedometer", "mdi:alert"
        self._min = vp_min
        self._max = vp_max
        self._step = vp_step
        self._mode = vp_mode
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

    @property
    def state(self):
        """Return the state of the number."""
        return self._state

    @property
    def vp_reg(self):
        """Return the device class of the number."""
        return self._vp_reg

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def native_min_value(self):
        """Return the min value."""
        return self._min

    @property
    def native_max_value(self):
        """Return the max value."""
        return self._max

    @property
    def native_step(self):
        """Return the step."""
        return self._step

    @property
    def mode(self):
        """Return the mode (box/slider)."""
        return self._mode

    @property
    def icon(self):
        """Return the icon of the number."""
        return self._icon

    @property
    def device_class(self):
        """Return the class of this device."""
        return f"{DOMAIN}_HeatPumpNumber"

    async def async_set_value(self, value: float) -> None:
        if value != self._heatpump._hpstate[self._vp_reg]:
            self._heatpump._hpstate[self._vp_reg] = value
            await self._heatpump.send_mqtt_reg(self._idx, value)
            await self._heatpump._hass.bus.fire(
                # This will reload all sensor entities in this heatpump
                f"{self._heatpump._domain}__msg_rec_event",
                {},
            )

    async def async_update(self):
        """Update the value of the entity."""
        """Update the new state of the sensor."""

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
