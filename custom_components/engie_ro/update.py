from __future__ import annotations

import logging

import aiohttp
from homeassistant.components.update import UpdateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
REPO = "boogytotyo/engie_ro"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
HTML_RELEASE = f"https://github.com/{REPO}/releases"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([EngieUpdateEntity(hass, entry)], True)


class EngieUpdateEntity(UpdateEntity):
    _attr_has_entity_name = True
    _attr_name = "Engie România update"
    _attr_unique_id = "engie_ro_update"
    _attr_entity_registry_visible_default = True
    _attr_release_url: str | None = None
    _attr_release_summary: str | None = None

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._installed_version = None
        # Citește versiunea din manifest
        try:
            import json
            import os

            manifest_path = os.path.join(
                hass.config.path(), "custom_components", "engie_ro", "manifest.json"
            )
            if os.path.exists(manifest_path):
                self._installed_version = json.load(open(manifest_path, encoding="utf-8")).get(
                    "version"
                )
        except Exception:  # best-effort
            pass
        self._latest_version = self._installed_version
        self._attr_release_url = HTML_RELEASE

    @property
    def installed_version(self) -> str | None:
        return self._installed_version

    @property
    def latest_version(self) -> str | None:
        return self._latest_version

    async def async_update(self) -> None:
        # Interoghează GitHub pentru ultima versiune
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    API_URL, headers={"Accept": "application/vnd.github+json"}
                ) as resp:
                    if resp.status != 200:
                        _LOGGER.debug("GitHub latest release returned %s", resp.status)
                        return
                    data = await resp.json()
                    tag = data.get("tag_name") or data.get("name")
                    body = data.get("body")
                    html_url = data.get("html_url") or HTML_RELEASE
                    if tag:
                        self._latest_version = str(tag).lstrip("v")
                    self._attr_release_summary = body
                    self._attr_release_url = html_url
        except TimeoutError:
            _LOGGER.debug("Timeout checking GitHub releases")
        except Exception as exc:
            _LOGGER.debug("Error checking GitHub releases: %s", exc)

    @property
    def release_url(self) -> str | None:
        return self._attr_release_url

    @property
    def release_summary(self) -> str | None:
        return self._attr_release_summary

    @property
    def device_info(self) -> DeviceInfo | None:
        return DeviceInfo(
            identifiers={(DOMAIN, "engie_ro")},
            name="Engie România",
            manufacturer="ENGIE",
        )
