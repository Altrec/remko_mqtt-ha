import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import UnitOfTemperature
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
    FIELD_UNIT,
    FIELD_MINVALUE,
    FIELD_MAXVALUE,
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
    entities: list[NumberEntity] = []

    for key, meta in reg_id.items():
        if (
            meta[FIELD_REGTYPE] == "sensor_temp_inp"
            and meta[FIELD_REGNUM] in heatpump._capabilities
        ):
            device_id = key
            friendly_name = id_names.get(key, [None])[heatpump._langid]
            vp_reg = meta[FIELD_REGNUM]
            vp_type = meta[FIELD_REGTYPE]
            vp_unit = meta[FIELD_UNIT]
            vp_min = meta[FIELD_MINVALUE]
            vp_max = meta[FIELD_MAXVALUE]
            vp_step = 0.5
            vp_mode = "box"

            entities.append(
                HeatPumpNumber(
                    hass,
                    heatpump,
                    device_id,
                    vp_reg,
                    friendly_name,
                    vp_type,
                    vp_unit,
                    vp_min,
                    vp_max,
                    vp_step,
                    vp_mode,
                )
            )
    async_add_entities(entities)


class HeatPumpNumber(NumberEntity):
    """Common functionality for Remko MQTT number entities."""

    __slots__ = ("hass", "_heatpump", "_vp_reg", "_idx")

    def __init__(
        self,
        hass: HomeAssistant,
        heatpump: Any,
        device_id: str,
        vp_reg: str,
        friendly_name: str | None,
        vp_type: str,
        vp_unit: str,
        vp_min: float,
        vp_max: float,
        vp_step: float,
        vp_mode: str,
    ) -> None:
        self.hass = hass
        self._heatpump = heatpump

        # Entity identifiers and naming
        self._attr_unique_id = f"{heatpump._domain}_{device_id}"
        self._attr_name = friendly_name
        self._attr_has_entity_name = True

        _LOGGER.debug(
            "creating number entity %s for idx %s", self._attr_unique_id, device_id
        )

        # Availability / presentation
        self._attr_icon = (
            "mdi:temperature-celsius"
            if vp_type in ("sensor_temp", "sensor_temp_inp") or vp_unit == "C"
            else "mdi:gauge"
        )
        self._attr_available = True

        # Native value / limits
        if vp_type in ("sensor_temp", "sensor_temp_inp") or vp_unit == "C":
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        else:
            self._attr_native_unit_of_measurement = vp_unit or None

        self._attr_native_min_value = vp_min
        self._attr_native_max_value = vp_max
        self._attr_native_step = vp_step
        self._attr_mode = NumberMode(vp_mode)

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
        """No need to poll; updates are pushed via events."""
        return False

    async def async_added_to_hass(self) -> None:
        """Register event listener when entity is added to hass."""

        @callback
        def _handle_event(event) -> None:
            # schedule update task to keep event handler loop-safe
            self.hass.async_create_task(self._async_update_event(event))

        listener = self.hass.bus.async_listen(
            f"{self._heatpump._domain}_{self._heatpump._id}_msg_rec_event",
            _handle_event,
        )
        # ensure cleanup when entity removed
        self.async_on_remove(listener)

    async def async_set_native_value(self, value: float) -> None:
        """Set new value and send register write via MQTT."""
        current = self._heatpump.get_value(self._vp_reg)
        if value != current:
            # update local cache and send MQTT write
            self._heatpump._hpstate[self._vp_reg] = value
            await self._heatpump.send_mqtt_reg(self._idx, value)
            # notify other entities for this heatpump (non-awaitable)
            self._heatpump._hass.bus.fire(
                f"{self._heatpump._domain}_{self._heatpump._id}_msg_rec_event", {}
            )

    async def async_update(self) -> None:
        """Fetch latest value from heatpump object."""
        _LOGGER.debug("update: %s", self._idx)
        value = self._heatpump.get_value(self._vp_reg)
        if value is None:
            _LOGGER.warning("Could not get data for %s", self._idx)
            self._attr_available = False
            return
        self._attr_available = True
        self._attr_native_value = value

    async def _async_update_event(self, event) -> None:
        """Handle update event and refresh state if changed."""
        _LOGGER.debug("event: %s", self._idx)
        value = self._heatpump.get_value(self._vp_reg)
        if value is None:
            _LOGGER.debug("Could not get data for %s", self._idx)
            return

        if getattr(self, "_attr_native_value", None) != value:
            self._attr_native_value = value
            self.async_schedule_update_ha_state()
            _LOGGER.debug("async_update_ha: %s -> %s", self._idx, value)
