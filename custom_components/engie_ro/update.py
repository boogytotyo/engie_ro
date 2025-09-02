from __future__ import annotations

from homeassistant.components.update import UpdateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    version = data["version"]
    async_add_entities([EngieUpdateEntity(coordinator, entry, version)], True)


class EngieUpdateEntity(UpdateEntity):
    _attr_name = "Engie România update"
    _attr_entity_picture = "https://brands.home-assistant.io/_/engie_ro/icon.png"

    def __init__(self, coordinator, entry: ConfigEntry, version: str) -> None:
        self._entry = entry
        self._coordinator = coordinator
        self._installed = version

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_update_entity"

    @property
    def installed_version(self) -> str | None:
        return self._installed

    @property
    def latest_version(self) -> str | None:
        # dacă nu vrei request suplimentar, păstrezi aceeași versiune;
        # poți extinde cu GitHub Releases dacă dorești
        return self._installed

    @property
    def supported_features(self) -> int:
        # none → 0
        return 0

    @property
    def entity_picture(self) -> str | None:
        return "https://brands.home-assistant.io/_/engie_ro/icon.png"
