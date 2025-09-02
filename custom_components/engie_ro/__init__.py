from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform

from .const import (
    DOMAIN,
    PLATFORMS,
    DEFAULT_UPDATE_INTERVAL,
    CONF_UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

type EngieConfigEntry = ConfigEntry

async def async_setup_entry(hass: HomeAssistant, entry: EngieConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    update_interval = int(entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL))
    if update_interval < DEFAULT_UPDATE_INTERVAL:
        update_interval = max(update_interval, 300)

    from .coordinator import create_coordinator
    coordinator = await create_coordinator(hass, entry, timedelta(seconds=update_interval))
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
    return True

async def async_unload_entry(hass: HomeAssistant, entry: EngieConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, [Platform.SENSOR])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok

async def async_reload_entry(hass: HomeAssistant, entry: EngieConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
