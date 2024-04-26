import logging
from typing import List

from homeassistant.components.input_button import (
    InputButton,
    InputButtonStorageCollection,
)
from homeassistant.const import (
    CONF_ICON,
    CONF_ID,
    CONF_NAME,
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

from .const import CONF_ENTITY_PLATFORM, PLATFORM_INPUT_BUTTON

_LOGGER = logging.getLogger(__name__)

PLATFORM = PLATFORM_INPUT_BUTTON


class CustomInputButton(InputButton):
    register: str
    reg_id: str
    heatpump: HeatPump

    async def async_internal_added_to_hass(self):
        await Entity.async_internal_added_to_hass(self)

    async def async_internal_will_remove_from_hass(self):
        await Entity.async_internal_will_remove_from_hass(self)

    async def async_get_last_state(self):
        pass

    async def async_press(self) -> None:
        _LOGGER.debug("inp %s", self.entity_id)

        if self.heatpump._hpstate[self.reg] == False:
            value = int(1)
        else:
            value = int(0)
        await self.heatpump.send_mqtt_reg(self.reg_id, value)


async def setup_input_button(heatpump) -> None:
    """Setup input button."""

    await update_input_button(heatpump)


async def update_input_button(heatpump) -> None:
    """Update built in input button."""

    platform: EntityPlatform = heatpump._hass.data[CONF_ENTITY_PLATFORM][PLATFORM][0]
    to_add: List[CustomInputButton] = []
    entity_list = []

    for key in reg_id:
        if reg_id[key][1] in [
            "switch",
        ]:
            inp = create_input_button_entity(heatpump, key)
            to_add.append(inp)
            entity_list.append(f"{PLATFORM}.{heatpump._domain}" + "_" + key)

    await platform.async_add_entities(to_add)


def create_input_button_entity(heatpump, name) -> CustomInputButton:
    """Create a CustomInputBoolean instance."""

    entity_id = f"{heatpump._domain}_{name}"
    if name in id_names:
        friendly_name = id_names[name][heatpump._langid]
    else:
        friendly_name = None
    icon = None
    config = {
        CONF_ID: entity_id,
        CONF_NAME: friendly_name,
        CONF_ICON: icon,
    }

    entity = CustomInputButton.from_yaml(config)
    entity.reg = reg_id[name][0]
    entity.reg_id = name
    entity.heatpump = heatpump

    return entity
