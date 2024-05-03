import logging
from homeassistant.core import callback
from typing import List


from homeassistant.components.select import SelectEntity
from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
)

from homeassistant.helpers.device_registry import DeviceEntryType

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
    hass, config_entry, async_add_entities, discovery_info=None
):
    """Set up platform for a new integration.

    Called by the HA framework after async_setup_platforms has been called
    during initialization of a new integration.
    """
    worker = hass.data[DOMAIN].worker
    heatpump = hass.data[DOMAIN]._heatpumps[config_entry.data[CONF_ID]]
    to_add: List[HeatPumpSelect] = []
    entities = []

    for key in reg_id:
        if reg_id[key][FIELD_REGTYPE] == "select_input":
            device_id = key
            if key in id_names:
                friendly_name = id_names[key][heatpump._langid]
            else:
                friendly_name = None
            vp_reg = reg_id[key][FIELD_REGNUM]
            vp_type = reg_id[key][FIELD_REGTYPE]

            vp_options = []

            if key == "main_mode":
                for i in range(1, 5):
                    mode = "mode" + str(i)
                    vp_options.append(id_names[mode][heatpump._langid])
            elif key == "dhw_opmode":
                for i in range(4):
                    mode = "dhwopmode" + str(i)
                    vp_options.append(id_names[mode][heatpump._langid])

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
    """Common functionality for all entities."""

    def __init__(
        self,
        hass,
        heatpump,
        device_id,
        vp_reg,
        friendly_name,
        vp_type,
        vp_options,
    ):
        self.hass = hass
        self._heatpump = heatpump
        self._hpstate = heatpump._hpstate

        # set HA instance attributes directly (mostly don't use property)
        self._attr_unique_id = f"{heatpump._domain}_{device_id}"
        self.entity_id = f"select.{heatpump._domain}_{device_id}"

        _LOGGER.debug("entity_id:" + self.entity_id)
        _LOGGER.debug("idx:" + device_id)
        self._name = friendly_name
        self._state = None
        self._options = vp_options
        self._icon = "mdi:gauge"
        # "mdi:thermometer" ,"mdi:oil-temperature", "mdi:gauge", "mdi:speedometer", "mdi:alert"

        self._entity_picture = None
        self._available = True

        self._idx = device_id
        self._vp_reg = vp_reg

        # Listen for the Remko rec event indicating new data
        hass.bus.async_listen(
            heatpump._domain + "_" + heatpump._id + "_msg_rec_event",
            self._async_update_event,
        )

        self._attr_device_info = {
            ATTR_IDENTIFIERS: {(heatpump._id, "Remko-MQTT")},
            ATTR_NAME: CONF_NAME,
            ATTR_MANUFACTURER: "Remko",
            ATTR_MODEL: CONF_VER,
            "entry_type": DeviceEntryType.SERVICE,
        }

    @property
    def name(self):
        """Return the name of the select entity."""
        return self._name

    @property
    def should_poll(self):
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def state(self):
        """Return the state of the select entity."""
        return self._state

    @property
    def vp_reg(self):
        """Return the device class of the select entity."""
        return self._vp_reg

    @property
    def options(self):
        return self._options

    @property
    def icon(self):
        """Return the icon of the select entity."""
        return self._icon

    @property
    def device_class(self):
        """Return the class of this device."""
        return f"{DOMAIN}_HeatPumpSelect"

    async def async_select_option(self, option: str) -> None:
        value = self._options.index(option)
        if value != self._options.index(self._heatpump._hpstate[self._vp_reg]):
            self._heatpump._hpstate[self._vp_reg] = option
            self._heatpump._hass.bus.fire(
                # This will reload all sensor entities in this heatpump
                f"{self._heatpump._domain}__msg_rec_event",
                {},
            )
            await self._heatpump.send_mqtt_reg(self._idx, value)

    async def _async_update_event(self, event):
        """Update the new state of the select entity."""

        _LOGGER.debug("event: " + self._idx)
        state = self._hpstate[self._vp_reg]
        if state is None:
            _LOGGER.debug("Could not get data for %s", self._idx)
        if self._state is None or self._state != state:
            self._state = state
            self.async_schedule_update_ha_state()
            _LOGGER.debug("async_update_ha: %s", str(state))
