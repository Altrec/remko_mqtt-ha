import logging
from typing import Any, Literal

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.device_registry import DeviceEntryType

from .const import DOMAIN, CONF_ID, CONF_NAME, CONF_VER
from .remko_regs import FIELD_REGNUM, FIELD_REGTYPE, id_names, reg_id

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: dict | None = None,
) -> None:
    """Set up platform for a new integration."""
    heatpump = hass.data[DOMAIN]._heatpumps[config_entry.data[CONF_ID]]
    entities: list[ButtonEntity] = []

    for device_id, meta in reg_id.items():
        if meta[FIELD_REGTYPE] != "action":
            continue

        friendly_name = id_names.get(device_id, [None])[heatpump._langid]
        vp_reg = meta[FIELD_REGNUM]

        entities.append(
            HeatPumpButton(
                hass,
                heatpump,
                device_id,
                vp_reg,
                friendly_name,
            )
        )

    async_add_entities(entities)


class HeatPumpButton(ButtonEntity):
    """Remko MQTT actionable button entity."""

    __slots__ = (
        "hass",
        "_heatpump",
        "_hpstate",
        "_vp_reg",
        "_idx",
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

        # Unique id should not contain integration domain per guidelines
        self._attr_unique_id = f"{heatpump._id}_{device_id}"
        self._attr_name = friendly_name
        self._attr_has_entity_name = True

        _LOGGER.debug(
            "creating button entity %s for idx %s", self._attr_unique_id, device_id
        )

        # icon/availability
        self._attr_icon = "mdi:heat-wave" if device_id == "dhw_heating" else "mdi:gauge"
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
    def should_poll(self) -> bool:
        """No polling; updates are pushed via events."""
        return False

    @property
    def vp_reg(self) -> str:
        """Return the device register id."""
        return self._vp_reg

    @property
    def device_class(self) -> str:
        """Return a device class string for this integration."""
        return f"{DOMAIN}_HeatPumpButton"

    async def async_press(self) -> None:
        """Handle button press by sending register write via MQTT."""
        await self._heatpump.send_mqtt_reg(self._idx, 0)
