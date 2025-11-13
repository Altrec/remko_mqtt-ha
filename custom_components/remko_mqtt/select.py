import logging
from typing import Any, List

from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.select import SelectEntity
from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
)
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    DOMAIN,
    CONF_ID,
    CONF_NAME,
    CONF_VER,
)

from .remko_regs import (
    FIELD_REGNUM,
    FIELD_REGTYPE,
    id_names,
    reg_id,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: dict | None = None,
) -> None:
    """Set up platform for a new integration."""
    heatpump = hass.data[DOMAIN]._heatpumps[config_entry.data[CONF_ID]]
    entities: List[HeatPumpSelect] = []

    for key, meta in reg_id.items():
        if meta[FIELD_REGTYPE] != "select_input":
            continue
        if meta[FIELD_REGNUM] not in heatpump._capabilites:
            continue

        device_id = key
        friendly_name = id_names.get(key, [None])[heatpump._langid]
        vp_reg = meta[FIELD_REGNUM]
        vp_type = meta[FIELD_REGTYPE]

        if key == "main_mode":
            vp_options = [id_names[f"mode{i}"][heatpump._langid] for i in range(1, 5)]
        elif key == "dhw_opmode":
            vp_options = [id_names[f"dhwopmode{i}"][heatpump._langid] for i in range(4)]
        elif key == "timemode":
            vp_options = [id_names[f"timemode{i}"][heatpump._langid] for i in range(2)]
        elif key == "user_profile":
            vp_options = [
                id_names[f"user_profile{i}"][heatpump._langid] for i in range(3)
            ]
        else:
            vp_options = []

        entities.append(
            HeatPumpSelect(
                hass,
                heatpump,
                device_id,
                vp_reg,
                friendly_name,
                vp_type,
                vp_options,
            )
        )

    async_add_entities(entities)


class HeatPumpSelect(SelectEntity):
    """Select entity for Remko MQTT heatpump"""

    __slots__ = (
        "hass",
        "_heatpump",
        "_hpstate",
        "_idx",
        "_vp_reg",
        "_options",
        "_name",
        "_icon",
    )

    def __init__(
        self,
        hass: HomeAssistant,
        heatpump: Any,
        device_id: str,
        vp_reg: str,
        friendly_name: str | None,
        vp_type: str,
        vp_options: List[str],
    ) -> None:
        self.hass = hass
        self._heatpump = heatpump
        self._hpstate = heatpump._hpstate

        self._attr_unique_id = f"{heatpump._id}_{device_id}"
        self._attr_name = friendly_name
        self._attr_has_entity_name = True

        _LOGGER.debug(
            "creating select entity %s for idx %s", self._attr_unique_id, device_id
        )

        self._name = friendly_name
        self._state: str | None = None
        self._options = vp_options
        self._icon = "mdi:gauge"

        self._entity_picture = None
        self._attr_available = True

        self._idx = device_id
        self._vp_reg = vp_reg

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, heatpump._id)},
            name=CONF_NAME,
            manufacturer="Remko",
            model=CONF_VER,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def name(self) -> str | None:
        """Return the name of the select entity."""
        return self._name

    @property
    def should_poll(self) -> bool:
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def state(self) -> str | None:
        """Return the state of the select entity."""
        return self._state

    @property
    def vp_reg(self) -> str:
        """Return the device register id."""
        return self._vp_reg

    @property
    def options(self) -> List[str]:
        """Return the options for this select."""
        return list(self._options)

    @property
    def icon(self) -> str:
        """Return the icon of the select entity."""
        return self._icon

    @property
    def device_class(self) -> str:
        """Return the class of this device."""
        return f"{DOMAIN}_HeatPumpSelect"

    async def async_added_to_hass(self) -> None:
        """Register bus listener when entity is added to hass."""
        event_name = f"{self._heatpump._domain}_{self._heatpump._id}_msg_rec_event"

        @callback
        def _handle_event(event) -> None:
            # schedule coroutine-safe update
            self.hass.async_create_task(self._async_update_event(event))

        listener = self.hass.bus.async_listen(event_name, _handle_event)
        self.async_on_remove(listener)

    async def async_select_option(self, option: str) -> None:
        """Select a new option and write it to the device via MQTT."""
        try:
            value_index = self._options.index(option)
        except ValueError:
            _LOGGER.debug("Option %s not valid for %s", option, self._attr_unique_id)
            return

        current = self._heatpump._hpstate.get(self._vp_reg)
        # try to determine current index if stored as option string
        current_index = None
        if isinstance(current, str):
            try:
                current_index = self._options.index(current)
            except ValueError:
                current_index = None
        elif isinstance(current, int):
            current_index = current

        if value_index == current_index:
            return

        # update local cache to selected label and send to device
        self._heatpump._hpstate[self._vp_reg] = option
        # notify other entities for this heatpump
        self._heatpump._hass.bus.fire(
            f"{self._heatpump._domain}_{self._heatpump._id}_msg_rec_event", {}
        )
        await self._heatpump.send_mqtt_reg(self._idx, value_index)

    async def _async_update_event(self, event) -> None:
        """Update the new state of the select entity."""
        _LOGGER.debug("event: %s", self._idx)
        state = self._hpstate.get(self._vp_reg)
        if state is None:
            _LOGGER.debug("Could not get data for %s", self._idx)
            return

        if self._state != state:
            self._state = state
            self.async_schedule_update_ha_state()
            _LOGGER.debug("async_update_ha: %s -> %s", self._idx, str(state))
