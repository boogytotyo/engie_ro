from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

import aiohttp
from homeassistant.components.update import UpdateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class EngieUpdateEntity(UpdateEntity):
    _attr_unique_id = "engie_ro_update"
    _attr_entity_registry_visible_default = True
    _attr_release_url: str | None = None
    _attr_release_summary: str | None = None

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._installed_version: str | None = None
        self._latest_version: str | None = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "engie_ro_update")},
            name="Engie România (Update)",
        )

        # Citește versiunea din manifest (best-effort)
        try:
            manifest_path = os.path.join(hass.config.path(), "custom_components", "engie_ro", "manifest.json")
            if os.path.exists(manifest_path):
                with open(manifest_path, encoding="utf-8") as f:
                    self._installed_version = json.load(f).get("version")
        except Exception:  # noqa: BLE001
            pass

    @property
    def installed_version(self) -> str | None:
        return self._installed_version

    @property
    def latest_version(self) -> str | None:
        return self._latest_version

    async def async_update(self) -> None:
        # Verifică cel mai nou release din GitHub (best-effort, nu stricăm platforma dacă pică)
        url = "https://api.github.com/repos/boogytotyo/engie_ro/releases/latest"
        timeout = aiohttp.ClientTimeout(total=10)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers={"Accept": "application/vnd.github+json"}) as resp:
                    if resp.status != 200:
                        return
                    data: dict[str, Any] = await resp.json()
                    self._latest_version = data.get("tag_name") or data.get("name")
                    self._attr_release_summary = data.get("name")
                    self._attr_release_url = data.get("html_url")
        except TimeoutError:
            _LOGGER.debug("Timeout checking GitHub releases")
        except Exception as exc:  # noqa: BLE001
            _LOGGER.debug("Error checking GitHub releases: %s", exc)

    @property
    def release_url(self) -> str | None:
        return self._attr_release_url

    @property
    def release_summary(self) -> str | None:
        return self._attr_release_summary
