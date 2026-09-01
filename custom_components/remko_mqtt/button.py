"""Module for Remko MQTT button integration."""

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_ID, CONF_NAME, CONF_VER, DOMAIN
from .heatpump import HeatPump
from .remko_regs import (
    FIELD_ACTIVE,
    FIELD_REGID,
    FIELD_REGTYPE,
    get_remko_regs,
    remko_reg_translation,
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
    heatpump = hass.data[DOMAIN].get_heatpump(config_entry.data[CONF_ID])
    entities: list[ButtonEntity] = []

    # Register-Map für das spezifische Wärmepumpen-Modell abrufen
    registers = get_remko_regs(heatpump.model)

    for reg_name, reg_data in registers.items():
        reg_type = reg_data[FIELD_REGTYPE]
        reg_id = reg_data[FIELD_REGID]
        active = reg_data.get(FIELD_ACTIVE, True)

        # Only create buttons for action type
        if reg_type not in _BUTTON_TYPES:
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
            HeatPumpButton(
                hass=hass,
                heatpump=heatpump,
                config_entry=config_entry,
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

    _attr_has_entity_name = False
    _attr_available = True

    def __init__(
        self,
        hass: HomeAssistant,
        heatpump: HeatPump,
        config_entry: ConfigEntry,
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
        self._attr_unique_id = f"{heatpump.id}_{reg_name}"
        self._attr_name = friendly_name
        self._attr_icon = _ICON_MAPPING.get(reg_type, _DEFAULT_ICON)
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

        _LOGGER.debug(
            "Creating button entity %s for register %s", self._attr_unique_id, reg_name
        )

    @property
    def device_class(self) -> str:
        """Return the device class of this button."""
        return f"{DOMAIN}_HeatPumpButton"

    async def async_press(self) -> None:
        """Handle button press by sending action command via MQTT."""
        _LOGGER.debug("Button pressed: %s", self._reg_name)
        await self._heatpump.send_mqtt_reg(self._reg_name, 0)
