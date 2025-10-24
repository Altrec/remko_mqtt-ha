"""Component for Remko-MQTT support."""

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, Event
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED

from .const import (
    DOMAIN,
    CONF_ID,
)

from .heatpump import HeatPump

_LOGGER = logging.getLogger(__name__)


PLATFORMS = [
    "binary_sensor",
    "sensor",
    "switch",
    "number",
    "select",
    "button",
]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Remko-MQTT integration."""
    _LOGGER.info("Set up Remko-MQTT integration")
    hass.data.setdefault(DOMAIN, RemkoWorker(hass))
    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate configuration entry if needed"""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up component from a config entry."""
    _LOGGER.info("Set up Remko-MQTT integration entry %s", entry.data[CONF_ID])

    # One common RemkoWorker serves all HeatPump objects
    worker = hass.data.setdefault(DOMAIN, RemkoWorker(hass))

    # add new heatpump to worker
    heatpump = await worker.add_entry(entry)

    # Register update listener and ensure it is cleaned up on unload
    unload_update_listener = entry.add_update_listener(reload_entry)
    entry.async_on_unload(unload_update_listener)

    async def handle_hass_started(_event: Event) -> None:
        await hass.async_create_task(heatpump.setup_mqtt())

    await hass.async_create_task(heatpump.check_capabilities())

    # Load the platforms for heatpump
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    )

    if hass.is_running:
        # Immediately start MQTT setup if HA already running
        await hass.async_create_task(heatpump.setup_mqtt())
    else:
        # Wait for hass to start and then setup mqtt
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, handle_hass_started)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        worker: RemkoWorker = hass.data[DOMAIN]
        await hass.async_create_task(
            worker.update_heatpump_entry(entry)
        ) if False else None
        worker.remove_entry(entry)
        if worker.is_idle():
            # also remove worker if not used by any entry any more
            hass.data.pop(DOMAIN, None)

    return unload_ok


async def reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    if DOMAIN in hass.data:
        worker: RemkoWorker = hass.data[DOMAIN]
        await worker.update_heatpump_entry(entry)


class RemkoWorker:
    """Worker object. Stored in hass.data."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the instance."""
        self._hass = hass
        self._heatpumps: dict[str, Any] = {}
        self._worker = True

    @property
    def worker(self) -> bool:
        return self._worker

    @property
    def heatpumps(self) -> dict:
        return self._heatpumps

    async def add_entry(self, config_entry: ConfigEntry) -> HeatPump:
        """Add entry and create HeatPump instance."""
        heatpump = HeatPump(self._hass, config_entry)
        await heatpump.update_config(config_entry)
        self._heatpumps[config_entry.data[CONF_ID]] = heatpump
        self._hass.bus.fire(
            f"{DOMAIN}_changed",
            {"action": "add", "heatpump": config_entry.data[CONF_ID]},
        )
        return heatpump

    def remove_entry(self, config_entry: ConfigEntry) -> None:
        """Remove entry if present."""
        self._hass.bus.fire(
            f"{DOMAIN}_changed",
            {"action": "remove", "heatpump": config_entry.data[CONF_ID]},
        )
        # pop safely to avoid KeyError
        self._heatpumps.pop(config_entry.data[CONF_ID], None)

    async def update_heatpump_entry(self, config_entry: ConfigEntry) -> None:
        """Update heatpump configuration and restart MQTT setup."""
        hp = self._heatpumps.get(config_entry.data[CONF_ID])
        if not hp:
            return
        await hp.update_config(config_entry)
        await self._hass.async_create_task(hp.setup_mqtt())

    def is_idle(self) -> bool:
        return not bool(self._heatpumps)
