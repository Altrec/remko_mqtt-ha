import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import (
    UnitOfTemperature,
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
)
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo

from .timeprogram_converter import RemkoTimeProgramConverter

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
        """Add a Remko sensor property"""
        async_add_entities([sensor], True)
        # _LOGGER.debug('Added new sensor %s / %s', sensor.entity_id, sensor.unique_id)

    worker = hass.data[DOMAIN].worker
    heatpump = hass.data[DOMAIN]._heatpumps[config_entry.data[CONF_ID]]
    entities = []

    for key in reg_id:
        if (
            reg_id[key][FIELD_REGTYPE]
            in [
                "sensor",
                "sensor_counter",
                "sensor_el",
                "sensor_en",
                "sensor_input",
                "sensor_mode",
                "sensor_temp",
                "timeprogram",
            ]
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
                HeatPumpSensor(
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


class HeatPumpSensor(SensorEntity):
    """Common functionality for Remko MQTT sensors."""

    __slots__ = (
        "hass",
        "_heatpump",
        "_idx",
        "_vp_reg",
        "_vp_type",
        "_name",
        "_unit",
        "_icon",
        "_state",
    )

    def __init__(
        self,
        hass: HomeAssistant,
        heatpump: Any,
        device_id: str,
        vp_reg: str,
        friendly_name: str | None,
        vp_type: str,
        vp_unit: str | None,
    ) -> None:
        self.hass = hass
        self._heatpump = heatpump

        if vp_type not in (
            "generated_sensor",
            "sensor_counter",
            "sensor_en",
            "sensor_mode",
            "timeprogram",
        ):
            self._attr_state_class = SensorStateClass.MEASUREMENT
        if vp_type in ("sensor_counter", "sensor_en"):
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING

        # unique id should not include platform name
        self._attr_unique_id = f"{heatpump._id}_{device_id}"
        self._attr_has_entity_name = True

        self._name = friendly_name
        self._state = None
        if vp_type == "sensor_temp":
            self._icon = "mdi:temperature-celsius"
            self._unit = UnitOfTemperature.CELSIUS
        elif vp_type == "sensor_en":
            self._icon = "mdi:lightning-bolt"
            self._unit = vp_unit
        elif vp_type == "sensor_counter":
            self._icon = "mdi:counter"
            self._unit = vp_unit
        elif vp_type == "timeprogram":
            self._icon = "mdi:calendar-clock"
            self._unit = None
        else:
            self._icon = "mdi:gauge"
            self._unit = vp_unit or None

        self._entity_picture = None
        self._attr_available = True

        self._idx = device_id
        self._vp_reg = vp_reg
        self._vp_type = vp_type

        self._previous_timeprogram = None

        # device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, heatpump._id)},
            name=CONF_NAME,
            manufacturer="Remko",
            model=CONF_VER,
            entry_type=DeviceEntryType.SERVICE,
        )

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
        """Return the state of the sensor."""
        return self._state

    @property
    def vp_reg(self):
        """Return the device class of the sensor."""
        return self._vp_reg

    @property
    def vp_type(self):
        """Return the device type of the sensor."""
        return self._vp_type

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._icon

    @property
    def extra_state_attributes(self) -> dict:
        """Return timeprogram attributes for this sensor's register."""
        if not hasattr(self, "_heatpump"):
            return {}

        tp = self._heatpump._hpstate.get(self._vp_reg)
        if isinstance(tp, dict) and "mon" in tp:
            return {"timeprogram": tp}
        return {}

    async def async_added_to_hass(self) -> None:
        # MQTT Event Listener
        @callback
        def _handle_event(event) -> None:
            self.hass.async_create_task(self._async_update_event(event))

        mqtt_listener = self.hass.bus.async_listen(
            f"{self._heatpump._domain}_{self._heatpump._id}_msg_rec_event",
            _handle_event,
        )
        self.async_on_remove(mqtt_listener)
        _LOGGER.debug(f"MQTT event listener registered")

        # Time program Update Event Listener
        @callback
        def _handle_timeprogram_update_event(event) -> None:
            """Schedule async worker for timeprogram events (per-entity)."""
            self.hass.async_create_task(self._process_timeprogram_event(event))

        event_name = f"{DOMAIN}_timeprogram_updated"
        _LOGGER.debug("Listening for event: '%s'", event_name)
        timeprogram_listener = self.hass.bus.async_listen(
            event_name, _handle_timeprogram_update_event
        )
        self.async_on_remove(timeprogram_listener)

    _LOGGER.debug("Time program update event listener registered!")

    async def _process_timeprogram_event(self, event) -> None:
        """Handle a timeprogram update event targeted at a specific entity."""
        event_entity_id = event.data.get("entity_id")
        timeprogram = event.data.get("timeprogram")

        _LOGGER.debug(
            "Timeprogram event for %s (self=%s)", event_entity_id, self.entity_id
        )
        if event_entity_id != self.entity_id:
            return

        if not (timeprogram and isinstance(timeprogram, dict)):
            _LOGGER.error("Time program is not a dict for %s", self.entity_id)
            return

        # Save locally and convert to device format
        self._previous_timeprogram = timeprogram
        _LOGGER.debug("Time program saved for %s", self.entity_id)

        try:
            timeprogram_value = RemkoTimeProgramConverter.timeprogram_to_hex(
                timeprogram
            )
        except Exception as err:  # conversion failure should not crash HA
            _LOGGER.exception(
                "Failed converting timeprogram for %s: %s", self.entity_id, err
            )
            return

        # Update device/state
        # send_mqtt_reg expects the device index (device id) as used elsewhere
        await self._heatpump.send_mqtt_reg(self._idx, timeprogram_value)
        # update local cache (heatpump may also update on incoming MQTT message)
        self._heatpump._hpstate[self._vp_reg] = timeprogram
        # notify HA
        self.async_write_ha_state()
        _LOGGER.debug("Timeprogram written for %s", self.entity_id)

    async def async_update(self) -> None:
        """Fetch latest value from the heatpump object."""
        _LOGGER.debug("update: %s", self._idx)
        value = self._heatpump.get_value(self._vp_reg)

        if self._vp_type == "timeprogram":
            # Timeprogram entity shows as 'loaded' while detailed program
            # is available in extra_state_attributes
            if isinstance(value, dict):
                # value is the stored timeprogram dict
                self._state = "loaded"
                self._attr_available = True
                return
            value = "loaded"
        if value is None:
            _LOGGER.warning("Could not get data for %s", self._idx)
            self._attr_available = False
            return
        self._attr_available = True
        self._state = value

    async def _async_update_event(self, event) -> None:
        """Handle event: update state from heatpump cache and notify HA if changed."""
        _LOGGER.debug("event: %s", self._idx)
        value = self._heatpump.get_value(self._vp_reg)

        if self._vp_type == "timeprogram":
            # show generic state for timeprogram; details are in attributes
            if isinstance(value, dict):
                new_state = "loaded"
            else:
                new_state = "loaded"
            value = new_state
        if value is None:
            _LOGGER.debug("Could not get data for %s", self._idx)
            return
        if self._state != value:
            self._state = value
            # schedule HA state update (use sync scheduler available on Entity)
            self.schedule_update_ha_state()
            _LOGGER.debug("async_update_ha: %s -> %s", self._idx, str(value))

        self.async_write_ha_state()

    @property
    def device_class(self):
        """Return the class of this device."""
        # Propper device class needed for e.g. energy dashboard
        if self._unit == UnitOfTemperature.CELSIUS:
            return "temperature"
        if self._unit == "kWh":
            return "energy"
        if self._unit == "W":
            return "power"

        return f"{DOMAIN}_HeatPumpSensor"
