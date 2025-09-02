from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import EngieClient, EngieUnauthorized
from .auth import EngieMobileAuth
from .const import (
    AUTH_MODE_MOBILE,
    CONF_AUTH_MODE,
    CONF_BASE_URL,
    CONF_BEARER_TOKEN,
    CONF_DEVICE_ID,
    CONF_PASSWORD,
    CONF_TOKEN_FILE,
    CONF_USERNAME,
    DEFAULT_BASE_URL,
    DEFAULT_TOKEN_FILE,
    DOMAIN,
    UPDATE_INTERVAL_SEC,
)

LOGGER = logging.getLogger(__name__)


@dataclass
class EngieTokens:
    token: str
    refresh_token: str | None
    exp: Any | None
    refresh_epoch: Any | None


class EngieDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass, LOGGER, name=DOMAIN, update_interval=timedelta(seconds=UPDATE_INTERVAL_SEC)
        )
        self.entry = entry
        self._session: aiohttp.ClientSession | None = None
        self._client: EngieClient | None = None
        self._base_url = (entry.data.get(CONF_BASE_URL) or DEFAULT_BASE_URL).rstrip("/")
        self._auth_mode = (entry.data.get(CONF_AUTH_MODE) or AUTH_MODE_MOBILE).strip()
        self._username = (entry.data.get(CONF_USERNAME) or "").strip()
        self._password = (entry.data.get(CONF_PASSWORD) or "").strip()
        self._device_id = (entry.data.get(CONF_DEVICE_ID) or "").strip()
        self._bearer = (entry.data.get(CONF_BEARER_TOKEN) or "").strip()
        self._token_file = (entry.data.get(CONF_TOKEN_FILE) or DEFAULT_TOKEN_FILE).strip()
        self._tokens: EngieTokens | None = None

    async def _session_get(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        return self._session

    async def _load_token_file(self) -> str | None:
        try:
            with open(self._token_file, encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            return None

    async def _save_token_file(self, token: str) -> None:
        try:
            with open(self._token_file, "w", encoding="utf-8") as f:
                f.write(token)
        except Exception as e:
            LOGGER.debug("Could not save token file: %s", e)

    async def _ensure_client(self) -> EngieClient:
        if self._client is None:
            s = await self._session_get()
            token = self._bearer or (await self._load_token_file()) or ""
            self._client = EngieClient(self._base_url, token=token, session=s)
        return self._client

    async def _login_mobile_if_needed(self) -> None:
        """If mobile mode, ensure token exists; otherwise skip."""
        if self._auth_mode != AUTH_MODE_MOBILE:
            return
        token = (await self._load_token_file()) or ""
        if token:
            return
        auth = EngieMobileAuth(self._base_url, session=await self._session_get())
        token, refresh, exp, refresh_epoch = await auth.login(
            self._username, self._password, self._device_id or "device"
        )
        await auth.close()
        await self._save_token_file(token)
        # also update client
        self._client = EngieClient(self._base_url, token=token, session=await self._session_get())

    async def _async_update(self) -> dict[str, Any]:
        """Core fetch logic called by coordinator."""
        await self._login_mobile_if_needed()
        client = await self._ensure_client()

        # Example: status check (won't raise unless 401/4xx)
        try:
            await client.app_status_ok()
        except EngieUnauthorized:
            # try to re-login if in mobile mode
            if self._auth_mode == AUTH_MODE_MOBILE:
                await self._save_token_file("")  # drop
                await self._login_mobile_if_needed()
                client = await self._ensure_client()
            else:
                raise

        # Placeholder for actual data fetch flows; keep keys stable for sensors
        data: dict[str, Any] = {
            "user": {},
            "contracts": {},
            "indexes": {},
            "consumption": {},
            "balance": {},
            "invoices": {},
        }

        # (Exemplu de fetch — păstrăm cheile; logica exactă rămâne ca în sursa ta)
        try:
            # Aici ai apela client.get_balance / get_invoices_details / get_* conform logicii tale
            pass
        except Exception as e:
            LOGGER.debug("Fetch error: %s", e)

        return data

    async def _async_update_data(self) -> dict[str, Any]:
        return await self._async_update()
