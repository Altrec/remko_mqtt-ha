"""Input numbers used for settings."""
import logging
from typing import List

from homeassistant.components.input_number import (
    CONF_INITIAL,
    CONF_MAX,
    CONF_MIN,
    CONF_STEP,
    InputNumber,
    MODE_BOX,
)
from homeassistant.const import (
    CONF_ICON,
    CONF_ID,
    CONF_MODE,
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
    UnitOfTemperature,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import EntityPlatform

from .heatpump import HeatPump
from .heatpump.remko_regs import (
    FIELD_MAXVALUE,
    FIELD_MINVALUE,
    FIELD_REGNUM,
    FIELD_REGTYPE,
    FIELD_UNIT,
    id_names,
    reg_id,
)

from .const import CONF_ENTITY_PLATFORM, PLATFORM_INPUT_NUMBER

_LOGGER = logging.getLogger(__name__)


PLATFORM = PLATFORM_INPUT_NUMBER


class CustomInputNumber(InputNumber):
    register: str
    reg_id: str
    heatpump: HeatPump

    async def async_internal_added_to_hass(self):
        await Entity.async_internal_added_to_hass(self)

    async def async_internal_will_remove_from_hass(self):
        await Entity.async_internal_will_remove_from_hass(self)

    async def async_get_last_state(self):
        pass

    async def async_set_value(self, value):
        _LOGGER.debug("inp %s", self.entity_id)
        # We require that we have values from the hp before allowing updates from GUI
        await super().async_set_value(value)
        if value != self.heatpump._hpstate[self.reg]:
            self.heatpump._hpstate[self.reg] = value
            self.heatpump._hass.bus.fire(
                # This will reload all sensor entities in this heatpump
                f"{self.heatpump._domain}__msg_rec_event",
                {},
            )
            await self.heatpump.send_mqtt_reg(self.reg_id, value)


async def setup_input_numbers(heatpump) -> None:
    """Setup input numbers."""

    await update_input_numbers(heatpump)


async def update_input_numbers(heatpump) -> None:
    """Update built in input numbers."""

    platform: EntityPlatform = heatpump._hass.data[CONF_ENTITY_PLATFORM][PLATFORM][0]
    to_add: List[CustomInputNumber] = []
    entity_list = []

    for key in reg_id:
        if reg_id[key][1] in [
            "temperature_input",
            "sensor_input",
            "generated_input",
        ]:
            inp = create_input_number_entity(heatpump, key)
            to_add.append(inp)
            entity_list.append(f"{PLATFORM}.{heatpump._domain}" + "_" + key)

    await platform.async_add_entities(to_add)


def create_input_number_entity(heatpump, name) -> CustomInputNumber:
    """Create a CustomInputNumber instance."""

    entity_id = f"{heatpump._domain}_{name}"
    if name in id_names:
        friendly_name = id_names[name][heatpump._langid]
    else:
        friendly_name = None
    input_step = 1
    if name == "water_temp_req":
        input_step = 0.5
    icon = None
    unit = None
    if (
        reg_id[name][1]
        in [
            "temperature_input",
        ]
    ) or (
        reg_id[name][2]
        in [
            "C",
        ]
    ):
        icon = "mdi:temperature-celsius"
        unit = UnitOfTemperature.CELSIUS
    else:
        unit = reg_id[name][2]
        icon = "mdi:gauge"
    # "mdi:thermometer" ,"mdi:oil-temperature", "mdi:gauge", "mdi:speedometer", "mdi:alert"

    config = {
        CONF_ID: entity_id,
        CONF_NAME: friendly_name,
        CONF_MIN: reg_id[name][3],
        CONF_MAX: reg_id[name][4],
        CONF_STEP: input_step,
        CONF_ICON: icon,
        CONF_MODE: MODE_BOX,
        CONF_INITIAL: None,
        CONF_UNIT_OF_MEASUREMENT: unit,
    }

    entity = CustomInputNumber.from_yaml(config)
    entity.reg = reg_id[name][0]
    entity.reg_id = name
    entity.heatpump = heatpump

    return entity
