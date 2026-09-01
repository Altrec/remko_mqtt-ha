"""Module for Remko MQTT select input integration."""

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
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
_SELECT_TYPES = {"select_input"}
_DEFAULT_ICON = "mdi:gauge"

# Option ranges for each select register
_OPTION_CONFIG = {
    "main_mode": {"count": 4, "prefix": "mode", "start": 1},
    "dhw_opmode": {"count": 4, "prefix": "dhwopmode", "start": 0},
    "timemode": {"count": 2, "prefix": "timemode", "start": 0},
    "user_profile": {"count": 3, "prefix": "user_profile", "start": 0},
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: dict[str, Any] | None = None,
) -> None:
    """Set up select platform from config entry.

    Called by the HA framework after async_setup_platforms has been called
    during initialization of a new integration.
    """
    heatpump = hass.data[DOMAIN].get_heatpump(config_entry.data[CONF_ID])
    entities: list[SelectEntity] = []

    registers = get_remko_regs(heatpump.model)

    for reg_name, reg_data in registers.items():
        reg_type = reg_data[FIELD_REGTYPE]
        reg_id = reg_data[FIELD_REGID]
        active = reg_data.get(FIELD_ACTIVE, True)

        # Only create select entities for select_input type that are available
        if reg_type not in _SELECT_TYPES or reg_id not in heatpump.capabilities:
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

        # Get options for this select
        options = _get_select_options(reg_name, heatpump.langid)

        entities.append(
            HeatPumpSelect(
                hass=hass,
                heatpump=heatpump,
                config_entry=config_entry,
                reg_name=reg_name,
                reg_id=reg_id,
                active=active,
                friendly_name=friendly_name,
                options=options,
            )
        )

    async_add_entities(entities)


def _get_select_options(reg_name: str, langid: int) -> list[str]:
    """Get translated options for a select register."""
    if reg_name not in _OPTION_CONFIG:
        return []

    config = _OPTION_CONFIG[reg_name]
    options = []

    for i in range(config["start"], config["start"] + config["count"]):
        option_key = f"{config['prefix']}{i}"
        try:
            option_text = remko_reg_translation[option_key][langid]
            options.append(option_text)
        except KeyError, IndexError:
            _LOGGER.warning(
                "Could not get translation for option %s at language index %s",
                option_key,
                langid,
            )

    return options


class HeatPumpSelect(SelectEntity):
    """Select entity for Remko heat pump option registers."""

    _attr_has_entity_name = False
    _attr_available = True

    def __init__(
        self,
        hass: HomeAssistant,
        heatpump: HeatPump,
        config_entry: ConfigEntry,
        reg_name: str,
        reg_id: str,
        active: bool,
        friendly_name: str | None,
        options: list[str],
    ) -> None:
        """Initialize select entity."""
        self.hass = hass
        self._heatpump = heatpump

        # Entity metadata
        self._attr_unique_id = f"{heatpump.id}_{reg_name}"
        self._attr_name = friendly_name
        self._attr_icon = _DEFAULT_ICON
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

        # Options and state
        self._attr_options = options
        self._attr_current_option: str | None = None

        # Set entity registry enabled default based on active flag
        self._attr_entity_registry_enabled_default = active

        # Active flag
        self._active = active

        _LOGGER.debug(
            "Creating select entity %s for register %s with %d options",
            self._attr_unique_id,
            reg_name,
            len(options),
        )

    @property
    def device_class(self) -> str:
        """Return the device class of this select."""
        return f"{DOMAIN}_HeatPumpSelect"

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

    async def _async_update_from_event(self, event) -> None:
        """Handle MQTT event and update state if changed."""
        _LOGGER.debug("MQTT event received for %s", self._reg_name)

        value = self._heatpump.get_value(self._reg_id)

        if value is None:
            _LOGGER.debug("Could not retrieve value for %s", self._reg_name)
            return

        if self._attr_current_option != value:
            self._attr_current_option = value
            self.async_write_ha_state()
            _LOGGER.debug("State updated: %s -> %s", self._reg_name, value)

    async def async_select_option(self, option: str) -> None:
        """Select a new option and write it to the device via MQTT."""
        _LOGGER.debug("Selecting option for %s: %s", self._reg_name, option)

        # Get index of selected option
        try:
            option_index = self._attr_options.index(option)
        except ValueError:
            _LOGGER.error(
                "Option %s not valid for %s. Valid options: %s",
                option,
                self._attr_unique_id,
                self._attr_options,
            )
            return

        # Get current option/index
        current = self._heatpump.get_value(self._reg_id)
        current_index = None

        if isinstance(current, str):
            try:
                current_index = self._attr_options.index(current)
            except ValueError:
                current_index = None
        elif isinstance(current, int):
            current_index = current

        # Skip if no change
        if option_index == current_index:
            _LOGGER.debug("Option unchanged for %s, skipping send", self._reg_name)
            return

        # Send option index to heat pump
        await self._heatpump.send_mqtt_reg(self._reg_name, option_index)

        _LOGGER.info(
            "Option sent for %s: %s (index: %d)", self._reg_name, option, option_index
        )
