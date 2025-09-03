from __future__ import annotations
import aiohttp
from datetime import datetime, timedelta
from typing import Any, Dict, Tuple
from urllib.parse import quote_plus

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
        if not self.token:
            raise EngieHTTPError("No Bearer token configured.")
        return {
            "Accept": "application/json",
            "Accept-Language": "ro-RO,ro;q=0.9,en-US;q=0.8,en;q=0.7",
            "Authorization": f"Bearer {self.token}",
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
        h["Device-Id"] = device_id
        return h

    async def _get(self, path: str, params: Dict[str, Any] | None = None) -> Any:
        s = await self._session_get()
        url = f"{self.base_url}{path}"
        async with s.get(url, headers=self._headers(), params=params) as r:
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

    async def mobile_login(self, username: str, password: str, device_id: str) -> Tuple[str, str | None, int | None, int | None]:
        s = await self._session_get()
        url = f"{self.base_url}/v1/login"
        headers = self._headers_mobile(device_id)
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        payload = f"username={quote_plus(username)}&password={quote_plus(password)}"
        async with s.post(url, data=payload, headers=headers) as r:
            txt = await r.text()
            if r.status >= 400:
                raise EngieHTTPError(f"LOGIN -> {r.status}: {txt}")
            try:
                j = await r.json()
            except Exception as err:
                raise EngieHTTPError(f"LOGIN: non-JSON response: {txt}") from err
            data = j.get("data") if isinstance(j, dict) else None
            if not isinstance(data, dict):
                raise EngieHTTPError(f"LOGIN: unexpected JSON: {j}")
            token = str(data.get("token") or "")
            if not token:
                raise EngieHTTPError(f"LOGIN: token missing in response: {j}")
            refresh_token = data.get("refresh_token")
            exp = data.get("exp")
            refresh_epoch = data.get("refresh_token_expiration_date")
            return token, refresh_token, exp, refresh_epoch

    async def app_status_ok(self) -> bool:
        s = await self._session_get()
        url = f"{self.base_url}/v2/app_status"
        async with s.get(url, headers=self._headers()) as r:
            if r.status == 200:
                return True
            if r.status == 401:
                raise EngieUnauthorized("401 on app_status")
            txt = await r.text()
            if r.status >= 400:
                raise EngieHTTPError(f"app_status -> {r.status}: {txt}")
            return True

    # Data endpoints
    async def get_user(self) -> Any:
        return await self._get("/v1/user/me")

    async def get_places(self) -> Any:
        return await self._get("/v1/placesofconsumption")

    async def get_divisions(self, poc_number: str, pa: str | None = None) -> Any:
        params = {"pa": pa} if pa else None
        return await self._get(f"/v1/placesofconsumption/divisions/{poc_number}", params=params)

    async def get_index_window(self, poc_number: str, division: str = "gaz", pa: str | None = None, installation_number: str | None = None) -> Any:
        params: Dict[str, Any] = {"poc_number": poc_number, "division": division}
        if pa:
            params["pa"] = pa
        if installation_number:
            params["installation_number"] = installation_number
        return await self._get(f"/v1/index/{poc_number}", params=params)

    async def get_balance(self, contract_account: str) -> Any:
        try:
            return await self._post_form_json("/v1/widgets/ballance", {"contract_account[]": contract_account})
        except EngieHTTPError:
            return await self._post_form_json("/v1/widgets/ballance", {"contract_account": contract_account})

    async def get_invoices_details(self, contract_account: str) -> Any:
        try:
            return await self._post_form_json("/v1/invoices/ballance-details", {"contract_account[]": contract_account})
        except EngieHTTPError:
            return await self._post_form_json("/v1/invoices/ballance-details", {"contract_account": contract_account})

    async def get_consumption(self, poc_number: str, start_date: str, end_date: str, pa: str | None = None) -> Any:
        """GET /v1/index/consumption/{POC}?startDate=YYYY-MM-DD&endDate=YYYY-MM-DD&pa=PA"""
        params: Dict[str, Any] = {"startDate": start_date, "endDate": end_date}
        if pa:
            params["pa"] = pa
        return await self._get(f"/v1/index/consumption/{poc_number}", params=params)

    async def get_index_history_post(self, autocit: str, poc_number: str, division: str, start_date: str) -> Any:
        """POST /v1/index/history with JSON body."""
        payload = {
            "autocit": str(autocit),
            "poc_number": str(poc_number),
            "division": str(division),
            "start_date": str(start_date),
        }
        return await self._post_json("/v1/index/history", payload)    

    
    async def get_invoices_history(self, poc_number: str, start_date: str, end_date: str, pa: str | None = None) -> Any:
        """GET /v1/invoices/history-only/{POC}?startDate=YYYY-MM-DD&endDate=YYYY-MM-DD&pa=PA"""
        params: Dict[str, Any] = {"startDate": start_date, "endDate": end_date}
        if pa:
            params["pa"] = pa
        return await self._get(f"/v1/invoices/history-only/{poc_number}", params=params)
