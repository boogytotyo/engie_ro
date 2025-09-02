from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from aiohttp import ClientSession, ClientTimeout
from homeassistant.core import HomeAssistant

from .const import TOKEN_STORAGE_FILE, AuthError, TemporaryApiError

TIMEOUT = ClientTimeout(total=15)


class EngieApiClient:
    """Client HTTP pur, fără dependențe HA în metode."""
    def __init__(self, session: ClientSession, base_url: str = "https://gwss.engie.ro"):
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._token: str | None = None

    # ---------- Token file helpers ----------
    @staticmethod
    def _token_path(hass: HomeAssistant) -> Path:
        return Path(hass.config.path(TOKEN_STORAGE_FILE))

    @classmethod
    async def load_token(cls, hass: HomeAssistant) -> str | None:
        path = cls._token_path(hass)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data.get("token")
        except Exception:
            return None

    @classmethod
    async def save_token(cls, hass: HomeAssistant, token: str, meta: dict[str, Any] | None = None) -> None:
        path = cls._token_path(hass)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"token": token, "meta": meta or {}}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def set_runtime_token(self, token: str | None) -> None:
        self._token = token

    # ---------- Auth ----------
    async def login(self, email: str, password: str) -> str:
        """
        Autentificare username/password -> returnează Bearer token.
        NOTE: Înlocuiește cu endpointul real de autentificare.
        """
        url = f"{self._base_url}/myservices/v1/auth/login"  # TODO: endpoint exact
        payload = {"email": email, "password": password}

        async with self._session.post(url, json=payload, timeout=TIMEOUT) as resp:
            if resp.status == 401:
                raise AuthError("Invalid credentials")
            if resp.status in (429, 500, 502, 503, 504):
                raise TemporaryApiError(resp.status, "Temporary error on login")
            resp.raise_for_status()
            data = await resp.json()

        token = data.get("token") or data.get("access_token")
        if not token:
            raise AuthError("Token missing in login response")
        self._token = token
        return token

    # ---------- Helpers ----------
    async def _request_json(self, method: str, url: str, **kwargs) -> Any:
        assert self._token, "Missing bearer token"
        headers = kwargs.pop("headers", {})
        headers.setdefault("Accept", "application/json")
        headers.setdefault("Content-Type", "application/json")
        headers["Authorization"] = f"Bearer {self._token}"

        backoff = 1.5
        for attempt in range(4):
            try:
                async with self._session.request(method, url, headers=headers, timeout=TIMEOUT, **kwargs) as resp:
                    if resp.status == 401:
                        raise AuthError("Unauthorized (token expired/invalid)")
                    if resp.status in (429, 500, 502, 503, 504):
                        raise TemporaryApiError(resp.status, f"Temporary {resp.status}")
                    resp.raise_for_status()
                    return await resp.json()
            except TemporaryApiError:
                if attempt == 3:
                    raise
                await asyncio.sleep(backoff)
                backoff *= 2

    # ---------- High-level fetchers (normalizează răspunsuri) ----------
    async def fetch_account_overview(self) -> dict[str, Any]:
        # TODO: endpoints reale
        url = f"{self._base_url}/myservices/v1/account/overview"
        data = await self._request_json("GET", url)
        return data

    async def fetch_billing_history(self, pa: str, division: str, start_date: str) -> dict[str, Any]:
        url = f"{self._base_url}/myservices/v1/billing/history"
        payload = {"pa": pa, "division": division, "start_date": start_date}
        return await self._request_json("POST", url, json=payload)

    async def fetch_current_index(self, poc: str, division: str) -> dict[str, Any]:
        url = f"{self._base_url}/myservices/v1/index/current"
        payload = {"poc_number": poc, "division": division}
        return await self._request_json("POST", url, json=payload)
