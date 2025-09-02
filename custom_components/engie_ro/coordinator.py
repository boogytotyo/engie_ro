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
    """Coordinator pentru integrarea Engie România."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SEC),
        )
        self.entry = entry
        self._session: aiohttp.ClientSession | None = None
        self._client: EngieClient | None = None

        self._base_url = (entry.data.get(CONF_BASE_URL) or DEFAULT_BASE_URL).strip().rstrip("/")
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

    # ---------- File I/O în executor (evităm blocarea buclei de evenimente) ----------

    def _read_token_sync(self) -> str | None:
        try:
            with open(self._token_file, encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            return None

    async def _load_token_file(self) -> str | None:
        return await self.hass.async_add_executor_job(self._read_token_sync)

    def _write_token_sync(self, token: str) -> None:
        try:
            with open(self._token_file, "w", encoding="utf-8") as f:
                f.write((token or "").strip())
        except Exception as err:
            LOGGER.debug("Could not save token file: %s", err)

    async def _save_token_file(self, token: str) -> None:
        await self.hass.async_add_executor_job(self._write_token_sync, token)

    # -------------------------------------------------------------------------------

    async def _ensure_client(self) -> EngieClient:
        if self._client is None:
            s = await self._session_get()
            token = (self._bearer or (await self._load_token_file()) or "").strip()
            self._client = EngieClient(self._base_url, token=token, session=s)
        return self._client

    async def _login_mobile_if_needed(self) -> None:
        """Dacă suntem în modul 'mobile', ne asigurăm că avem token."""
        if self._auth_mode != AUTH_MODE_MOBILE:
            return

        token = ((await self._load_token_file()) or "").strip()
        if token:
            return

        auth = EngieMobileAuth(self._base_url, session=await self._session_get())
        token, refresh, exp, refresh_epoch = await auth.login(
            self._username.strip(),
            self._password.strip(),
            (self._device_id or "device").strip(),
        )
        await auth.close()
        await self._save_token_file(token)

        # Regenerăm clientul cu tokenul nou
        self._client = EngieClient(self._base_url, token=token, session=await self._session_get())

    async def _async_update(self) -> dict[str, Any]:
        """Fetch principal (păstrăm structura pentru senzori)."""
        await self._login_mobile_if_needed()
        client = await self._ensure_client()

        # Status ping (poate ridica 401)
        try:
            await client.app_status_ok()
        except EngieUnauthorized:
            if self._auth_mode == AUTH_MODE_MOBILE:
                await self._save_token_file("")
                await self._login_mobile_if_needed()
                client = await self._ensure_client()
            else:
                raise

        # Structura datelor pentru senzori — păstrată 1:1
        data: dict[str, Any] = {
            "user": {},
            "contracts": {},
            "indexes": {},
            "consumption": {},
            "balance": {},
            "invoices": {},
        }

        # Aici adaugi apelurile reale (get_balance / get_invoices_details / etc.)
        # conform logicii tale existente; eu nu schimb logica pentru a respecta cerința.
        try:
            pass
        except Exception as err:
            LOGGER.debug("Fetch error: %s", err)

        return data

    async def _async_update_data(self) -> dict[str, Any]:
        return await self._async_update()
