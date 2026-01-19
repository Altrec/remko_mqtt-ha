"""Module for Remko MQTT button integration."""

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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
_BUTTON_TYPES = {"action"}
_ICON_MAPPING = {
    "dhw_heating": "mdi:heat-wave",
}
_DEFAULT_ICON = "mdi:gauge"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: dict[str, Any] | None = None,
) -> None:
    """Set up button platform from config entry.

    Called by the HA framework after async_setup_platforms has been called
    during initialization of a new integration.
    """
    heatpump = hass.data[DOMAIN]._heatpumps[config_entry.data[CONF_ID]]
    entities: list[ButtonEntity] = []

    for reg_name, reg_data in remko_reg.items():
        reg_type = reg_data[FIELD_REGTYPE]
        reg_id = reg_data[FIELD_REGID]
        active = (
            reg_data[FIELD_ACTIVE] != False
        )  # Default to True if FIELD_ACTIVE not present

        # Only create buttons for action type
        if reg_type not in _BUTTON_TYPES:
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
            HeatPumpButton(
                hass=hass,
                heatpump=heatpump,
                reg_name=reg_name,
                reg_id=reg_id,
                reg_type=reg_type,
                active=active,
                friendly_name=friendly_name,
            )
        )

    async_add_entities(entities)


class HeatPumpButton(ButtonEntity):
    """Button entity for Remko heat pump action registers."""

    _attr_has_entity_name = True
    _attr_available = True

    def __init__(
        self,
        hass: HomeAssistant,
        heatpump: Any,
        reg_name: str,
        reg_id: str,
        reg_type: str,
        active: bool,
        friendly_name: str | None,
    ) -> None:
        """Initialize button entity."""
        self.hass = hass
        self._heatpump = heatpump

        # Entity metadata
        self._attr_unique_id = f"{heatpump._id}_{reg_name}"
        self._attr_name = friendly_name
        self._attr_icon = _ICON_MAPPING.get(reg_type, _DEFAULT_ICON)
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

        # Active flag
        self._active = active

        _LOGGER.debug(
            "Creating button entity %s for register %s", self._attr_unique_id, reg_name
        )

    @property
    def device_class(self) -> str:
        """Return the device class of this button."""
        return f"{DOMAIN}_HeatPumpButton"

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

    async def async_press(self) -> None:
        """Handle button press by sending action command via MQTT."""
        _LOGGER.debug("Button pressed:   %s", self._reg_name)
        await self._heatpump.send_mqtt_reg(self._reg_name, 0)
