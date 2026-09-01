"""Module for Remko MQTT number input integration."""

import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_ID, CONF_NAME, CONF_VER, DOMAIN
from .heatpump import HeatPump
from .remko_regs import (
    FIELD_ACTIVE,
    FIELD_MAXVALUE,
    FIELD_MINVALUE,
    FIELD_REGID,
    FIELD_REGTYPE,
    FIELD_UNIT,
    get_remko_regs,
    remko_reg_translation,
)

_LOGGER = logging.getLogger(__name__)

# Constants
_NUMBER_TYPES = {"sensor_temp_inp"}
_TEMPERATURE_TYPES = {"sensor_temp", "sensor_temp_inp"}
_TEMPERATURE_UNITS = {"C", "°C"}
_DEFAULT_STEP = 0.5
_TEMPERATURE_ICON = "mdi:temperature-celsius"
_DEFAULT_ICON = "mdi:gauge"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: dict[str, Any] | None = None,
) -> None:
    """Set up number platform from config entry.

    Called by the HA framework after async_setup_platforms has been called
    during initialization of a new integration.
    """
    heatpump = hass.data[DOMAIN].get_heatpump(config_entry.data[CONF_ID])
    entities: list[NumberEntity] = []

    # Register-Map für das spezifische Wärmepumpen-Modell abrufen
    registers = get_remko_regs(heatpump.model)

    for reg_name, reg_data in registers.items():
        reg_type = reg_data[FIELD_REGTYPE]
        reg_id = reg_data[FIELD_REGID]
        active = reg_data.get(FIELD_ACTIVE, True)

        # Only create number entities for sensor_temp_inp type that are available
        if reg_type not in _NUMBER_TYPES or reg_id not in heatpump.capabilities:
            continue

        # Get friendly name from translation
        friendly_name = None
        if reg_name in remko_reg_translation:
            try:
                friendly_name = remko_reg_translation[reg_name][heatpump.langid]
            except IndexError, KeyError:
                _LOGGER.warning(
                    "Could not get translation for %s at language index %s",
                    reg_name,
                    heatpump.langid,
                )

        entities.append(
            HeatPumpNumber(
                hass=hass,
                heatpump=heatpump,
                config_entry=config_entry,
                reg_name=reg_name,
                reg_id=reg_id,
                active=active,
                reg_type=reg_type,
                reg_unit=reg_data.get(FIELD_UNIT),
                reg_min=reg_data[FIELD_MINVALUE],
                reg_max=reg_data[FIELD_MAXVALUE],
                friendly_name=friendly_name,
            )
        )

    async_add_entities(entities)


class HeatPumpNumber(NumberEntity):
    """Number entity for Remko heat pump temperature input registers."""

    _attr_has_entity_name = False
    _attr_available = True
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        hass: HomeAssistant,
        heatpump: HeatPump,
        config_entry: ConfigEntry,
        reg_name: str,
        reg_id: str,
        active: bool,
        reg_type: str,
        reg_unit: str | None,
        reg_min: float,
        reg_max: float,
        friendly_name: str | None,
    ) -> None:
        """Initialize number entity."""
        self.hass = hass
        self._heatpump = heatpump

        # Entity metadata
        self._attr_unique_id = f"{heatpump.id}_{reg_name}"
        self._attr_name = friendly_name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, heatpump.id)},
            name=config_entry.data.get(CONF_NAME, "Remko Wärmepumpe"),
            manufacturer="Remko",
            model=config_entry.data.get(CONF_VER, "WKF"),
            entry_type=DeviceEntryType.SERVICE,
        )

        # Register metadata
        self._reg_name = reg_name
        self._reg_id = reg_id

        # Set entity registry enabled default based on active flag
        self._attr_entity_registry_enabled_default = active

        # Active flag
        self._active = active

        # Configure icon based on register type
        is_temperature = reg_type in _TEMPERATURE_TYPES or (
            reg_unit and reg_unit in _TEMPERATURE_UNITS
        )
        self._attr_icon = _TEMPERATURE_ICON if is_temperature else _DEFAULT_ICON

        # Configure units and limits
        if is_temperature:
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        else:
            self._attr_native_unit_of_measurement = reg_unit

        self._attr_native_min_value = reg_min
        self._attr_native_max_value = reg_max
        self._attr_native_step = _DEFAULT_STEP
        self._attr_native_value: float | None = None

        _LOGGER.debug(
            "Creating number entity %s for register %s (min: %s, max: %s)",
            self._attr_unique_id,
            reg_name,
            reg_min,
            reg_max,
        )

    async def async_added_to_hass(self) -> None:
        """Register MQTT event listener when entity is added to Home Assistant."""

        @callback
        def _handle_mqtt_event(event) -> None:
            """Handle MQTT message received event."""
            self.hass.async_create_task(self._async_update_from_event(event))

        mqtt_event = f"{self._heatpump.domain}_{self._heatpump.id}_msg_rec_event"
        listener = self.hass.bus.async_listen(mqtt_event, _handle_mqtt_event)
        self.async_on_remove(listener)
        _LOGGER.debug("MQTT event listener registered for %s", self.entity_id)

    async def async_update(self) -> None:
        """Fetch latest value from heat pump and update state."""
        _LOGGER.debug("Updating number entity state for %s", self._reg_name)
        value = self._heatpump.get_value(self._reg_id)

        if value is None:
            _LOGGER.warning("Could not retrieve value for %s", self._reg_name)
            self._attr_available = False
            return

        self._attr_available = True
        self._attr_native_value = value

    async def _async_update_from_event(self, event) -> None:
        """Handle MQTT event and update state if changed."""
        _LOGGER.debug("MQTT event received for %s", self._reg_name)
        value = self._heatpump.get_value(self._reg_id)

        if value is None:
            _LOGGER.debug("Could not retrieve value for %s", self._reg_name)
            return

        if self._attr_native_value != value:
            self._attr_native_value = value
            self.async_write_ha_state()
            _LOGGER.debug("State updated: %s -> %s", self._reg_name, value)

    async def async_set_native_value(self, value: float) -> None:
        """Set new value and send register write via MQTT."""
        _LOGGER.debug("Setting value for %s to %s", self._reg_name, value)

        current = self._heatpump.get_value(self._reg_id)

        # Only send if value actually changed
        if value == current:
            _LOGGER.debug("Value unchanged for %s, skipping send", self._reg_name)
            return

        # Send to heat pump
        await self._heatpump.send_mqtt_reg(self._reg_name, value)

        _LOGGER.info("Value sent for %s: %s", self._reg_name, value)
