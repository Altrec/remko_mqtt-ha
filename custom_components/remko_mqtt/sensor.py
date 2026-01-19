"""Module for Remko MQTT sensor integration."""

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import RegistryEntryDisabler

from .const import DOMAIN, CONF_ID, CONF_NAME, CONF_VER
from .remko_regs import (
    FIELD_REGID,
    FIELD_REGTYPE,
    FIELD_UNIT,
    FIELD_ACTIVE,
    remko_reg_translation,
    remko_reg,
)
from .timeprogram_converter import RemkoTimeProgramConverter

_LOGGER = logging.getLogger(__name__)

# Constants
_SENSOR_TYPES = {
    "sensor",
    "sensor_counter",
    "sensor_el",
    "sensor_en",
    "sensor_input",
    "sensor_mode",
    "sensor_temp",
    "timeprogram",
}

_STATE_CLASS_MAPPING = {
    "sensor_counter": SensorStateClass.TOTAL_INCREASING,
    "sensor_en": SensorStateClass.TOTAL_INCREASING,
}

_ICON_MAPPING = {
    "sensor_temp": "mdi:temperature-celsius",
    "sensor_en": "mdi:lightning-bolt",
    "sensor_counter": "mdi:counter",
    "timeprogram": "mdi:calendar-clock",
}

_UNIT_MAPPING = {
    "sensor_temp": UnitOfTemperature.CELSIUS,
}

_DEFAULT_ICON = "mdi:gauge"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: dict[str, Any] | None = None,
) -> None:
    """Set up sensor platform from config entry.

    Called by the HA framework after async_setup_platforms has been called
    during initialization of a new integration.
    """
    heatpump = hass.data[DOMAIN]._heatpumps[config_entry.data[CONF_ID]]
    entities = []

    for reg_name, reg_data in remko_reg.items():
        reg_type = reg_data[FIELD_REGTYPE]
        reg_id = reg_data[FIELD_REGID]
        active = (
            reg_data[FIELD_ACTIVE] != False
        )  # Default to True if FIELD_ACTIVE not present

        # Only create sensors for supported types that are available
        if reg_type not in _SENSOR_TYPES or reg_id not in heatpump._capabilities:
            continue

        # Get friendly name from translation (list indexed by language)
        friendly_name = None
        if reg_name in remko_reg_translation:
            try:
                friendly_name = remko_reg_translation[reg_name][heatpump._langid]
            except (IndexError, KeyError):
                _LOGGER.warning(
                    "Could not get translation for %s at language index %s",
                    reg_name,
                    heatpump._langid,
                )

        entities.append(
            HeatPumpSensor(
                hass=hass,
                heatpump=heatpump,
                reg_name=reg_name,
                reg_id=reg_id,
                active=active,
                reg_type=reg_type,
                reg_unit=reg_data[FIELD_UNIT],
                friendly_name=friendly_name,
            )
        )

    async_add_entities(entities)


class HeatPumpSensor(SensorEntity):
    """Sensor entity for Remko heat pump registers."""

    _attr_has_entity_name = True
    _attr_available = True

    def __init__(
        self,
        hass: HomeAssistant,
        heatpump: Any,
        reg_name: str,
        reg_id: str,
        active: bool,
        reg_type: str,
        reg_unit: str | None,
        friendly_name: str | None,
    ) -> None:
        """Initialize sensor entity."""
        self.hass = hass
        self._heatpump = heatpump

        # Entity metadata
        self._attr_unique_id = f"{heatpump._id}_{reg_name}"
        self._attr_name = friendly_name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, heatpump._id)},
            name=CONF_NAME,
            manufacturer="Remko",
            model=CONF_VER,
            entry_type=DeviceEntryType.SERVICE,
        )

        # Register metadata
        self._reg_name = reg_name
        self._reg_id = reg_id
        self._reg_type = reg_type

        # State
        self._state = None
        self._previous_timeprogram = None

        # Active flag
        self._active = active

        # Configure based on register type
        self._configure_sensor_type(reg_type, reg_unit)

    @property
    def state(self) -> Any:
        """Return the state of the sensor."""
        return self._state

    @property
    def device_class(self) -> str | None:
        """Return the device class of this sensor."""
        unit = self._attr_native_unit_of_measurement
        if unit == "°C":
            return "temperature"
        elif unit == "kWh":
            return "energy"
        elif unit == "W":
            return "power"
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return timeprogram attributes for this sensor's register."""
        if self._reg_type != "timeprogram":
            return {}

        timeprogram = self._heatpump._hpstate.get(self._reg_id)
        if isinstance(timeprogram, dict) and "mon" in timeprogram:
            return {"timeprogram": timeprogram}
        return {}

    @staticmethod
    async def _disable_entity(
        hass: HomeAssistant, entity_id: str, disabled: bool
    ) -> None:
        """Programmatically hide/show entity via registry."""
        entity_registry = er.async_get(hass)
        if entry := entity_registry.async_get(entity_id):
            disabled_by = RegistryEntryDisabler.INTEGRATION if disabled else None
            entity_registry.async_update_entity(
                entry.entity_id, disabled_by=disabled_by
            )

    def _configure_sensor_type(self, reg_type: str, reg_unit: str | None) -> None:
        """Configure sensor attributes based on register type."""
        # State class
        if reg_type in _STATE_CLASS_MAPPING:
            self._attr_state_class = _STATE_CLASS_MAPPING[reg_type]
        elif reg_type not in ("generated_sensor", "sensor_mode", "timeprogram"):
            self._attr_state_class = SensorStateClass.MEASUREMENT

        # Icon
        self._attr_icon = _ICON_MAPPING.get(reg_type, _DEFAULT_ICON)

        # Unit of measurement
        if reg_type in _UNIT_MAPPING:
            self._attr_native_unit_of_measurement = _UNIT_MAPPING[reg_type]
        else:
            self._attr_native_unit_of_measurement = reg_unit or None

    async def async_added_to_hass(self) -> None:
        """Register event listeners when entity is added to Home Assistant."""

        # MQTT data update listener
        @callback
        def _handle_mqtt_event(event) -> None:
            """Handle MQTT message received event."""
            self.hass.async_create_task(self._async_update_from_event(event))

        mqtt_event = f"{self._heatpump._domain}_{self._heatpump._id}_msg_rec_event"
        mqtt_listener = self.hass.bus.async_listen(mqtt_event, _handle_mqtt_event)
        self.async_on_remove(mqtt_listener)
        _LOGGER.debug("MQTT event listener registered for %s", self.entity_id)

        # Disable entity if active=False
        if not self._active:
            await self._disable_entity(self.hass, self.entity_id, True)
            _LOGGER.debug("Disabled entity %s (active=False)", self.entity_id)

        # Timeprogram update listener (only for timeprogram sensors)
        if self._reg_type == "timeprogram":

            @callback
            def _handle_timeprogram_event(event) -> None:
                """Handle timeprogram update event."""
                self.hass.async_create_task(self._process_timeprogram_event(event))

            event_name = f"{DOMAIN}_timeprogram_updated"
            timeprogram_listener = self.hass.bus.async_listen(
                event_name, _handle_timeprogram_event
            )
            self.async_on_remove(timeprogram_listener)
            _LOGGER.debug(
                "Timeprogram event listener registered for %s", self.entity_id
            )

    async def _async_update_from_event(self, event) -> None:
        """Update state from MQTT event."""
        _LOGGER.debug("MQTT event received for %s", self._reg_name)

        value = self._heatpump.get_value(self._reg_id)

        if value is None:
            _LOGGER.debug("Could not retrieve data for %s", self._reg_name)
            return

        # For timeprogram, set state to "loaded" instead of the dict
        if self._reg_type == "timeprogram":
            if isinstance(value, dict):
                new_state = "loaded"
            else:
                return
        else:
            new_state = value

        if self._state != new_state:
            self._state = new_state
            self.async_write_ha_state()
            _LOGGER.debug("State updated:  %s -> %s", self._reg_name, new_state)

    async def _process_timeprogram_event(self, event) -> None:
        """Handle timeprogram update event from service call."""
        event_entity_id = event.data.get("entity_id")
        timeprogram = event.data.get("timeprogram")

        _LOGGER.debug(
            "Timeprogram event for entity %s (self=%s)", event_entity_id, self.entity_id
        )

        # Ignore if not targeted at this entity
        if event_entity_id != self.entity_id:
            return

        # Validate timeprogram data
        if not isinstance(timeprogram, dict):
            _LOGGER.error(
                "Invalid timeprogram data for %s: expected dict, got %s",
                self.entity_id,
                type(timeprogram).__name__,
            )
            return

        # Save locally
        self._previous_timeprogram = timeprogram

        # Convert to device format
        try:
            timeprogram_hex = RemkoTimeProgramConverter.timeprogram_to_hex(timeprogram)
        except Exception as err:
            _LOGGER.exception(
                "Failed converting timeprogram for %s: %s", self.entity_id, err
            )
            return

        # Send to heat pump
        await self._heatpump.send_mqtt_reg(self._reg_name, timeprogram_hex)

        # Update local cache
        self._heatpump._hpstate[self._reg_id] = timeprogram

        # Notify Home Assistant
        self.async_write_ha_state()
        _LOGGER.debug("Timeprogram sent and state updated for %s", self.entity_id)

    async def async_update(self) -> None:
        """Fetch latest value from heat pump and update state."""
        _LOGGER.debug("Updating sensor state for %s", self._reg_name)

        value = self._heatpump.get_value(self._reg_id)

        if value is None:
            _LOGGER.warning("Could not retrieve value for %s", self._reg_name)
            self._attr_available = False
            return

        self._attr_available = True

        # For timeprogram, set state to "loaded" instead of the dict
        if self._reg_type == "timeprogram":
            if isinstance(value, dict):
                self._state = "loaded"
        else:
            self._state = value
