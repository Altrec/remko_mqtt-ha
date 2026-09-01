"""Module for Remko MQTT switch integration."""

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_ID, CONF_NAME, CONF_VER, DOMAIN
from .remko_regs import (
    FIELD_ACTIVE,
    FIELD_REGID,
    FIELD_REGTYPE,
    get_remko_regs,
    remko_reg_translation,
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
    """Set up switch platform from config entry."""
    heatpump = hass.data[DOMAIN].get_heatpump(config_entry.data[CONF_ID])
    entities: list[SwitchEntity] = []
    registers = get_remko_regs(heatpump.model)

    for reg_name, reg_data in registers.items():
        reg_type = reg_data[FIELD_REGTYPE]
        reg_id = reg_data[FIELD_REGID]
        active = reg_data.get(FIELD_ACTIVE, True)

        if reg_type not in _SWITCH_TYPES or reg_id not in heatpump.capabilities:
            continue

        friendly_name = None
        if reg_name in remko_reg_translation:
            try:
                friendly_name = remko_reg_translation[reg_name][heatpump.langid]
            except IndexError, KeyError:
                _LOGGER.warning(
                    "Could not get translation for %s at language index %s",
                    reg_name,
                    heatpump.lang_id,
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

    _attr_has_entity_name = False
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

        self._attr_unique_id = f"{heatpump.id}_{reg_name}"
        self._attr_name = friendly_name
        self._attr_icon = _ICON_MAPPING.get(reg_name, _DEFAULT_ICON)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, heatpump.id)},
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

        # Set entity registry enabled default based on active flag
        self._attr_entity_registry_enabled_default = active

        # Active flag
        self._active = active

        _LOGGER.debug(
            "Creating switch entity %s for register %s",
            self._attr_unique_id,
            reg_name,
        )

    async def async_added_to_hass(self) -> None:
        """Register MQTT event listener when entity is added to Home Assistant."""

        @callback
        def _handle_mqtt_event(event) -> None:
            """Handle MQTT message received event."""
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
                _LOGGER.debug("State updated: %s -> %s", self._reg_name, new_state)

        mqtt_event = f"{self._heatpump.domain}_{self._heatpump.id}_msg_rec_event"
        listener = self.hass.bus.async_listen(mqtt_event, _handle_mqtt_event)
        self.async_on_remove(listener)
        _LOGGER.debug("MQTT event listener registered for %s", self.entity_id)

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

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on by writing to the device via MQTT."""
        _LOGGER.debug("Turning on switch: %s", self._reg_name)
        await self._heatpump.send_mqtt_reg(self._reg_name, 1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off by writing to the device via MQTT."""
        _LOGGER.debug("Turning off switch: %s", self._reg_name)
        await self._heatpump.send_mqtt_reg(self._reg_name, 0)

    def _convert_to_bool(self, value: Any) -> bool:
        """Convert register value to boolean state."""
        try:
            return int(value) > 0
        except TypeError, ValueError:
            _LOGGER.debug(
                "Could not convert register value for %s to bool: %s",
                self._reg_name,
                value,
            )
            return False
