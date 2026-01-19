"""Module for Remko MQTT switch integration."""

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
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
    FIELD_ACTIVE,
    remko_reg_translation,
    remko_reg,
)

_LOGGER = logging.getLogger(__name__)

# Constants
_SWITCH_TYPES = {"switch"}
_ICON_MAPPING = {
    "absence_mode": "mdi:plane-car",
    "party_mode": "mdi:party-popper",
}
_DEFAULT_ICON = "mdi:gauge"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: dict[str, Any] | None = None,
) -> None:
    """Set up switch platform from config entry.

    Called by the HA framework after async_setup_platforms has been called
    during initialization of a new integration.
    """
    heatpump = hass.data[DOMAIN]._heatpumps[config_entry.data[CONF_ID]]
    entities: list[SwitchEntity] = []

    for reg_name, reg_data in remko_reg.items():
        reg_type = reg_data[FIELD_REGTYPE]
        reg_id = reg_data[FIELD_REGID]
        active = (
            reg_data[FIELD_ACTIVE] != False
        )  # Default to True if FIELD_ACTIVE not present

        # Only create switches for switch type that are available
        if reg_type not in _SWITCH_TYPES or reg_id not in heatpump._capabilities:
            continue

        # Get friendly name from translation
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
            HeatPumpSwitch(
                hass=hass,
                heatpump=heatpump,
                reg_name=reg_name,
                reg_id=reg_id,
                active=active,
                friendly_name=friendly_name,
            )
        )

    async_add_entities(entities)


class HeatPumpSwitch(SwitchEntity):
    """Switch entity for Remko heat pump on/off registers."""

    _attr_has_entity_name = True
    _attr_available = True

    def __init__(
        self,
        hass: HomeAssistant,
        heatpump: Any,
        reg_name: str,
        reg_id: str,
        active: bool,
        friendly_name: str | None,
    ) -> None:
        """Initialize switch entity."""
        self.hass = hass
        self._heatpump = heatpump

        # Entity metadata
        self._attr_unique_id = f"{heatpump._id}_{reg_name}"
        self._attr_name = friendly_name
        self._attr_icon = _ICON_MAPPING.get(reg_name, _DEFAULT_ICON)
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

        # State
        self._attr_is_on: bool | None = None

        # Active flag
        self._active = active

        _LOGGER.debug(
            "Creating switch entity %s for register %s",
            self._attr_unique_id,
            reg_name,
        )

    @property
    def device_class(self) -> str:
        """Return the device class of this switch."""
        return f"{DOMAIN}_HeatPumpSwitch"

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Hide if active is False."""
        return self._active

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

    async def async_added_to_hass(self) -> None:
        """Register MQTT event listener when entity is added to Home Assistant."""

        @callback
        def _handle_mqtt_event(event) -> None:
            """Handle MQTT message received event."""
            self.hass.async_create_task(self._async_update_from_event(event))

        mqtt_event = f"{self._heatpump._domain}_{self._heatpump._id}_msg_rec_event"
        listener = self.hass.bus.async_listen(mqtt_event, _handle_mqtt_event)
        self.async_on_remove(listener)
        _LOGGER.debug("MQTT event listener registered for %s", self.entity_id)

        # Disable entity if active=False
        if not self._active:
            await self._disable_entity(self.hass, self.entity_id, True)
            _LOGGER.debug("Disabled entity %s (active=False)", self.entity_id)

    async def async_update(self) -> None:
        """Fetch latest value from heat pump and update state."""
        _LOGGER.debug("Updating switch state for %s", self._reg_name)
        value = self._heatpump.get_value(self._reg_id)

        if value is None:
            _LOGGER.warning("Could not retrieve value for %s", self._reg_name)
            self._attr_available = False
            self._attr_is_on = None
            return

        self._attr_available = True
        self._attr_is_on = self._convert_to_bool(value)

    async def _async_update_from_event(self, event) -> None:
        """Handle MQTT event and update state if changed."""
        _LOGGER.debug("MQTT event received for %s", self._reg_name)
        value = self._heatpump.get_value(self._reg_id)

        if value is None:
            _LOGGER.debug("Could not retrieve value for %s", self._reg_name)
            self._attr_available = False
            new_state = None
        else:
            self._attr_available = True
            new_state = self._convert_to_bool(value)

        if self._attr_is_on != new_state:
            self._attr_is_on = new_state
            self.async_write_ha_state()
            _LOGGER.debug("State updated:   %s -> %s", self._reg_name, new_state)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on by writing to the device via MQTT."""
        _LOGGER.debug("Turning on switch:   %s", self._reg_name)
        await self._heatpump.send_mqtt_reg(self._reg_name, 1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off by writing to the device via MQTT."""
        _LOGGER.debug("Turning off switch:  %s", self._reg_name)
        await self._heatpump.send_mqtt_reg(self._reg_name, 0)

    def _convert_to_bool(self, value: Any) -> bool:
        """Convert register value to boolean state."""
        try:
            return int(value) > 0
        except (TypeError, ValueError):
            _LOGGER.debug(
                "Could not convert register value for %s to bool: %s",
                self._reg_name,
                value,
            )
            return False
