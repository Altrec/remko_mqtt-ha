"""Module for Remko MQTT binary sensor integration."""

import logging
from typing import Any, Literal

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info=None,
) -> None:
    """Set up platform for a new integration."""
    heatpump = hass.data[DOMAIN]._heatpumps[config_entry.data[CONF_ID]]
    entities: list[BinarySensorEntity] = []

    for key, meta in reg_id.items():
        if (
            meta[FIELD_REGTYPE] == "binary_sensor"
            and meta[FIELD_REGNUM] in heatpump._capabilites
        ):
            device_id = key
            friendly_name = (
                id_names.get(key, [None])[heatpump._langid] if key in id_names else None
            )
            vp_reg = meta[FIELD_REGNUM]
            vp_type = meta[FIELD_REGTYPE]
            vp_unit = meta[FIELD_UNIT]

            entities.append(
                HeatPumpBinarySensor(
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


class HeatPumpBinarySensor(BinarySensorEntity):
    """Common functionality for all entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        heatpump: Any,
        device_id: str,
        vp_reg: str,
        friendly_name: str | None,
        vp_type: str,
        vp_unit: str,
    ) -> None:
        self.hass = hass
        self._heatpump = heatpump

        # Entity identifiers and naming
        self._attr_unique_id = f"{heatpump._domain}_{device_id}"
        self._attr_name = friendly_name
        self._attr_has_entity_name = False

        _LOGGER.debug("creating entity %s for idx %s", self._attr_unique_id, device_id)

        self._state = None
        self._icon = "mdi:gauge"
        self._entity_picture = None
        self._available = True

        self._idx = device_id
        self._vp_reg = vp_reg
        self._remove_listener = None

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, heatpump._id)},
            name=CONF_NAME,
            manufacturer="Remko",
            model=CONF_VER,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def should_poll(self) -> bool:
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def state(self) -> Literal["on", "off"]:
        """Return the state of the sensor for legacy access."""
        return STATE_ON if self.is_on else STATE_OFF

    @property
    def vp_reg(self) -> str:
        """Return the device register id."""
        return self._vp_reg

    @property
    def is_on(self) -> bool:
        """Return True if sensor is on."""
        # Heatpump stores binary state as "01" or similar; compare accordingly
        return self._state == "01"

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        return self._icon

    async def async_added_to_hass(self) -> None:
        """Register bus listener when entity is added to hass."""

        @callback
        def _handle_event(event) -> None:
            # delegate to coroutine-safe updater
            self.hass.async_create_task(self._async_update_from_event(event))

        listener = self.hass.bus.async_listen(
            f"{self._heatpump._domain}_{self._heatpump._id}_msg_rec_event",
            _handle_event,
        )
        # Ensure listener is removed automatically when entity is removed
        self.async_on_remove(listener)

    async def async_update(self) -> None:
        """Update the value of the entity (called by HA when requested)."""
        _LOGGER.debug("update: %s", self._idx)
        value = self._heatpump.get_value(self._vp_reg)
        self._state = value
        if self._state is None:
            _LOGGER.warning("Could not get data for %s", self._idx)

    async def _async_update_from_event(self, event) -> None:
        """Handle update event from heatpump and refresh state."""
        _LOGGER.debug("event: %s", self._idx)
        value = self._heatpump.get_value(self._vp_reg)
        if value is None:
            _LOGGER.debug("Could not get data for %s", self._idx)
            return

        if self._state != value:
            self._state = value
            self.async_schedule_update_ha_state()
            _LOGGER.debug("async_update_ha: %s -> %s", self._idx, str(value))

    @property
    def device_class(self) -> str:
        """Return the class of this device."""
        return f"{DOMAIN}_HeatPumpSensor"
