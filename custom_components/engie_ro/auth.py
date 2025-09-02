from __future__ import annotations

from typing import Any

import aiohttp


class EngieAuthError(RuntimeError): ...


class EngieAuthUnauthorized(EngieAuthError): ...


class EngieMobileAuth:
    def __init__(self, base_url: str, session: aiohttp.ClientSession | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self._session = session

    async def _session_get(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        return self._session

    async def close(self) -> None:
        if self._session:
            await self._session.close()

    async def login(self, email: str, password: str, device_id: str) -> tuple[str, str, Any, Any]:
        s = await self._session_get()
        url = f"{self.base_url}/v2/login/mobile"
        payload: dict[str, Any] = {
            "email": (email or "").strip(),
            "password": (password or "").strip(),
            "device_id": (device_id or "").strip(),
        }
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "okhttp/4.12.0",
            "source": "android",
            "Device-Id": (device_id or "").strip(),
        }
        async with s.post(url, headers=headers, json=payload) as r:
            txt = await r.text()
            if r.status == 401:
                raise EngieAuthUnauthorized(f"mobile login -> 401: {txt}")
            if r.status >= 400:
                raise EngieAuthError(f"mobile login -> {r.status}: {txt}")
            try:
                j = await r.json()
            except Exception as err:
                raise EngieAuthError(f"mobile login non-JSON: {txt}") from err
            data = j.get("data") if isinstance(j, dict) else None
            if not isinstance(data, dict):
                raise EngieAuthError(f"mobile login unexpected JSON: {j}")
            token = str(data.get("token") or "").strip()
            if not token:
                raise EngieAuthError(f"mobile login: token missing: {j}")
            refresh_token = (data.get("refresh_token") or "").strip()
            exp = data.get("exp")
            refresh_epoch = data.get("refresh_token_expiration_date")
            return token, refresh_token, exp, refresh_epoch


class EngieBearerAuth:
    def __init__(self, bearer_token: str) -> None:
        self.bearer = (bearer_token or "").strip()

    def valid(self) -> bool:
        return bool(self.bearer)
