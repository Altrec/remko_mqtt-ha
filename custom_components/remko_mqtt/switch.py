import logging
from typing import Any, Literal

from homeassistant.core import HomeAssistant, callback
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.device_registry import DeviceEntryType

from homeassistant.const import STATE_OFF, STATE_ON, ATTR_IDENTIFIERS

from .const import DOMAIN, CONF_ID, CONF_NAME, CONF_VER
from .remko_regs import FIELD_REGNUM, FIELD_REGTYPE, id_names, reg_id

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: dict | None = None,
) -> None:
    """Set up switch entities for Remko MQTT integration."""
    heatpump = hass.data[DOMAIN]._heatpumps[config_entry.data[CONF_ID]]
    entities: list[SwitchEntity] = []

    for device_id, meta in reg_id.items():
        if meta[FIELD_REGTYPE] != "switch":
            continue
        if meta[FIELD_REGNUM] not in heatpump._capabilites:
            continue

        friendly_name = id_names.get(device_id, [None])[heatpump._langid]
        vp_reg = meta[FIELD_REGNUM]

        entities.append(
            HeatPumpSwitch(
                hass,
                heatpump,
                device_id,
                vp_reg,
                friendly_name,
            )
        )

    async_add_entities(entities)


class HeatPumpSwitch(SwitchEntity):
    """Remko MQTT switch entity."""

    __slots__ = (
        "hass",
        "_heatpump",
        "_hpstate",
        "_vp_reg",
        "_idx",
        "_name",
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
    ) -> None:
        self.hass = hass
        self._heatpump = heatpump
        self._hpstate = heatpump._hpstate

        self._attr_unique_id = f"{heatpump._id}_{device_id}"
        self._attr_has_entity_name = True
        self._attr_name = friendly_name

        _LOGGER.debug(
            "creating switch entity %s for idx %s", self._attr_unique_id, device_id
        )

        # Presentation
        if device_id == "absence_mode":
            self._icon = "mdi:plane-car"
        elif device_id == "party_mode":
            self._icon = "mdi:party-popper"
        else:
            self._icon = "mdi:gauge"

        self._attr_icon = self._icon
        self._attr_available = True

        self._idx = device_id
        self._vp_reg = vp_reg
        self._state: bool | None = None

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, heatpump._id)},
            name=CONF_NAME,
            manufacturer="Remko",
            model=CONF_VER,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def should_poll(self) -> bool:
        """No polling; updates are pushed via events."""
        return False

    @property
    def vp_reg(self) -> str:
        """Return the device register id."""
        return self._vp_reg

    @property
    def is_on(self) -> bool:
        """Return True if switch is on."""
        return bool(self._state)

    async def async_added_to_hass(self) -> None:
        """Register event listener when entity is added to hass."""
        event_name = f"{self._heatpump._domain}_{self._heatpump._id}_msg_rec_event"

        @callback
        def _handle_event(event) -> None:
            # schedule coroutine-safe update
            self.hass.async_create_task(self._async_update_event(event))

        listener = self.hass.bus.async_listen(event_name, _handle_event)
        # ensure listener is removed automatically when entity is removed
        self.async_on_remove(listener)

    async def async_turn_on(self) -> None:
        """Turn the switch on by writing to the device via MQTT."""
        await self._heatpump.send_mqtt_reg(self._idx, 1)

    async def async_turn_off(self) -> None:
        """Turn the switch off by writing to the device via MQTT."""
        await self._heatpump.send_mqtt_reg(self._idx, 0)

    async def async_update(self) -> None:
        """Fetch latest value from heatpump object."""
        _LOGGER.debug("update: %s", self._idx)
        reg_state = self._heatpump.get_value(self._vp_reg)
        if reg_state is None:
            _LOGGER.warning("Could not get data for %s", self._idx)
            self._attr_available = False
            self._state = None
            return

        self._attr_available = True
        try:
            self._state = int(reg_state) > 0
        except (TypeError, ValueError):
            _LOGGER.debug("Unexpected register value for %s: %s", self._idx, reg_state)
            self._state = False

    async def _async_update_event(self, event) -> None:
        """Handle incoming update event and refresh entity state."""
        _LOGGER.debug("event: %s", self._idx)
        reg_state = self._hpstate.get(self._vp_reg)
        if reg_state is None:
            _LOGGER.debug("Could not get data for %s", self._idx)
            self._attr_available = False
            new_state = None
        else:
            self._attr_available = True
            try:
                new_state = int(reg_state) > 0
            except (TypeError, ValueError):
                _LOGGER.debug(
                    "Unexpected register value for %s: %s", self._idx, reg_state
                )
                new_state = False

        if self._state != new_state:
            self._state = new_state
            self.async_write_ha_state()
            _LOGGER.debug(
                "async_update_ha: %s -> %s", self._idx, str(new_state or False)
            )

    @property
    def device_class(self) -> str:
        """Return the class of this device."""
        return f"{DOMAIN}_HeatPumpSwitch"
