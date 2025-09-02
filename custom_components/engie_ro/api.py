from __future__ import annotations
import aiohttp
from typing import Any, Dict, Tuple

class EngieHTTPError(RuntimeError): ...
class EngieUnauthorized(EngieHTTPError): ...

class EngieClient:
    def __init__(self, base_url: str, token: str = "", session: aiohttp.ClientSession | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = (token or "").strip()
        self._session = session
        self.android_headers = {
            "source": "android",
            "App-Version": "2.0.33",
            "App-Build": "161",
            "OS-Version": "6.0",
            "OS-Platform": "Android",
            "Device-Type": "phone",
            "Device-Manufacturer": "Vodafone",
            "Device-Model": "VFD 500",
            "Screen-Height": "854",
            "Screen-Width": "480",
            "User-Agent": "okhttp/4.12.0",
            "Accept": "application/json",
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
        }

    async def _session_get(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        return self._session

    async def close(self) -> None:
        if self._session:
            await self._session.close()

    def _headers(self) -> Dict[str, str]:
        token = (self.token or "").strip()
        if not token:
            raise EngieHTTPError("No Bearer token configured.")
        return {
            "Accept": "application/json",
            "Accept-Language": "ro-RO,ro;q=0.9,en-US;q=0.8,en;q=0.7",
            "Authorization": f"Bearer {token}",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Origin": "https://my.engie.ro",
            "Referer": "https://my.engie.ro/",
            "source": "desktop",
            "User-Agent": "Mozilla/5.0",
            "X-Requested-With": "XMLHttpRequest",
        }

    def _headers_mobile(self, device_id: str) -> Dict[str, str]:
        h = dict(self.android_headers)
        h["Device-Id"] = (device_id or "").strip()
        return h

    async def _get(self, path: str, params: Dict[str, str] | None = None) -> Any:
        s = await self._session_get()
        url = f"{self.base_url}{path}"
        async with s.get(url, headers=self._headers(), params=params or {}) as r:
            txt = await r.text()
            if r.status == 401:
                raise EngieUnauthorized(f"GET {path} -> 401: {txt}")
            if r.status >= 400:
                raise EngieHTTPError(f"GET {path} -> {r.status}: {txt}")
            try:
                return await r.json()
            except Exception:
                return txt

    async def _post_form_json(self, path: str, form: Dict[str, str]) -> Any:
        s = await self._session_get()
        url = f"{self.base_url}{path}"
        async with s.post(url, headers=self._headers(), data=form) as r:
            txt = await r.text()
            if r.status == 401:
                raise EngieUnauthorized(f"POST {path} -> 401: {txt}")
            if r.status >= 400:
                raise EngieHTTPError(f"POST {path} -> {r.status}: {txt}")
            try:
                return await r.json()
            except Exception:
                return txt

    async def _post_json(self, path: str, payload: Dict[str, Any]) -> Any:
        s = await self._session_get()
        url = f"{self.base_url}{path}"
        headers = dict(self._headers())
        headers["Content-Type"] = "application/json"
        async with s.post(url, headers=headers, json=payload) as r:
            txt = await r.text()
            if r.status == 401:
                raise EngieUnauthorized(f"POST {path} -> 401: {txt}")
            if r.status >= 400:
                raise EngieHTTPError(f"POST {path} -> {r.status}: {txt}")
            try:
                return await r.json()
            except Exception:
                return txt

    async def mobile_login(self, email: str, password: str, device_id: str) -> Tuple[str, str | None, Any, Any]:
        s = await self._session_get()
        url = f"{self.base_url}/v2/login/mobile"
        payload: Dict[str, Any] = {
            "email": (email or "").strip(),
            "password": (password or "").strip(),
            "device_id": (device_id or "").strip(),
        }
        headers = self._headers_mobile(device_id)
        headers["Content-Type"] = "application/json"
        async with s.post(url, headers=headers, json=payload) as r:
            txt = await r.text()
            if r.status == 401:
                raise EngieUnauthorized(f"LOGIN {url} -> 401: {txt}")
            if r.status >= 400:
                raise EngieHTTPError(f"LOGIN -> {r.status}: {txt}")
            try:
                j = await r.json()
            except Exception as err:
                raise EngieHTTPError(f"LOGIN: non-JSON response: {txt}") from err
            data = j.get("data") if isinstance(j, dict) else None
            if not isinstance(data, dict):
                raise EngieHTTPError(f"LOGIN: unexpected JSON: {j}")
            token = str(data.get("token") or "").strip()
            if not token:
                raise EngieHTTPError(f"LOGIN: token missing in response: {j}")
            refresh_token = (data.get("refresh_token") or "").strip()
            exp = data.get("exp")
            refresh_epoch = data.get("refresh_token_expiration_date")
            return token, refresh_token, exp, refresh_epoch