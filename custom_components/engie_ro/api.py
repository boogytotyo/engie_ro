from __future__ import annotations

import logging
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant

from .const import USER_AGENT

_LOGGER = logging.getLogger(__name__)


class EngieHTTPError(Exception):
    pass


def _explain_status(code: int) -> str:
    m = {
        200: "OK (200)",
        400: "Cerere invalidă (400)",
        401: "Autentificare eșuată (401)",
        403: "Acces refuzat (403)",
        404: "Resursă inexistentă (404)",
        429: "Prea multe cereri (429)",
        0: "Eroare rețea (0)",
    }
    return m.get(code, f"HTTP {code}")


class EngieClient:
    def __init__(self, hass: HomeAssistant, cfg: dict[str, Any]):
        self._hass = hass
        self._email = cfg.get("email")
        self._password = cfg.get("password")
        self._token: str | None = None
        self._session: aiohttp.ClientSession | None = None

    async def _session_get(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/json",
                }
            )
        return self._session

    async def _fetch(
        self, method: str, url: str, data: dict | None = None, use_auth: bool = True
    ) -> dict:
        s = await self._session_get()
        headers = {}
        if data is not None:
            headers["Content-Type"] = "application/json; charset=utf-8"
        if use_auth and self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        async with s.request(method, url, json=data, headers=headers) as r:
            txt = await r.text()
            try:
                j = await r.json()
            except Exception as err:
                raise EngieHTTPError(f"LOGIN: non-JSON response: {txt}") from err
            data = j.get("data") if isinstance(j, dict) else None
            if not isinstance(data, dict):
                raise EngieHTTPError(f"Eroare API {url} → {_explain_status(r.status)}")
            return data
