from __future__ import annotations

from typing import Any
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN

async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    coord = hass.data[DOMAIN].get(entry.entry_id)
    redacted = "***"
    return {
        "options": entry.options,
        "data": {**entry.data, "password": redacted},
        "coordinator_data_keys": list((coord.data or {}).keys()) if coord else [],
    }
