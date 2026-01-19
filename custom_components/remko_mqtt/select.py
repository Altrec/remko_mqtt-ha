"""Module for Remko MQTT select input integration."""

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
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
    heatpump = hass.data[DOMAIN]._heatpumps[config_entry.data[CONF_ID]]
    entities: list[SelectEntity] = []

    for reg_name, reg_data in remko_reg.items():
        reg_type = reg_data[FIELD_REGTYPE]
        reg_id = reg_data[FIELD_REGID]
        active = (
            reg_data[FIELD_ACTIVE] != False
        )  # Default to True if FIELD_ACTIVE not present

        # Only create select entities for select_input type that are available
        if reg_type not in _SELECT_TYPES or reg_id not in heatpump._capabilities:
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

        # Get options for this select
        options = _get_select_options(reg_name, heatpump._langid)

        entities.append(
            HeatPumpSelect(
                hass=hass,
                heatpump=heatpump,
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
        except (KeyError, IndexError):
            _LOGGER.warning(
                "Could not get translation for option %s at language index %s",
                option_key,
                langid,
            )

    return options


class HeatPumpSelect(SelectEntity):
    """Select entity for Remko heat pump option registers."""

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
        options: list[str],
    ) -> None:
        """Initialize select entity."""
        self.hass = hass
        self._heatpump = heatpump

        # Entity metadata
        self._attr_unique_id = f"{heatpump._id}_{reg_name}"
        self._attr_name = friendly_name
        self._attr_icon = _DEFAULT_ICON
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

        # Options and state
        self._attr_options = options
        self._attr_current_option: str | None = None

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
            _LOGGER.debug("State updated:   %s -> %s", self._reg_name, value)

    async def async_select_option(self, option: str) -> None:
        """Select a new option and write it to the device via MQTT."""
        _LOGGER.debug("Selecting option for %s:  %s", self._reg_name, option)

        # Get index of selected option
        try:
            option_index = self._attr_options.index(option)
        except ValueError:
            _LOGGER.error(
                "Option %s not valid for %s.  Valid options: %s",
                option,
                self._attr_unique_id,
                self._attr_options,
            )
            return

        # Get current option/index
        current = self._heatpump._hpstate.get(self._reg_id)
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

        # Update local cache with option string
        self._heatpump._hpstate[self._reg_id] = option

        # Send option index to heat pump
        await self._heatpump.send_mqtt_reg(self._reg_name, option_index)

        # Notify other entities
        self._heatpump._hass.bus.fire(
            f"{self._heatpump._domain}_{self._heatpump._id}_msg_rec_event", {}
        )

        _LOGGER.info(
            "Option sent for %s: %s (index:  %d)", self._reg_name, option, option_index
        )
