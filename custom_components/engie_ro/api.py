from __future__ import annotations

from typing import Any

import aiohttp


class EngieHTTPError(RuntimeError): ...


class EngieUnauthorized(EngieHTTPError): ...


class EngieClient:
    def __init__(
        self, base_url: str, token: str = "", session: aiohttp.ClientSession | None = None
    ) -> None:
        self.base_url = (base_url or "").strip().rstrip("/")
        self._session = session
        self._token = self._clean(token)
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

    @staticmethod
    def _clean(value: Any) -> str:
        """Remove CR/LF anywhere and trim."""
        s = str(value or "")
        return s.replace("\r", "").replace("\n", "").strip()

    @property
    def token(self) -> str:
        return self._token

    @token.setter
    def token(self, value: str) -> None:
        self._token = self._clean(value)

    async def _session_get(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        return self._session

    async def close(self) -> None:
        if self._session:
            await self._session.close()

    def _sanitize_headers(self, headers: dict[str, str]) -> dict[str, str]:
        # Remove any CR/LF from all header values.
        return {k: self._clean(v) for k, v in headers.items()}

    def _headers(self) -> dict[str, str]:
        token = self._clean(self._token)
        if not token:
            raise EngieHTTPError("No Bearer token configured.")
        headers = {
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
        return self._sanitize_headers(headers)

    def _headers_mobile(self, device_id: str) -> dict[str, str]:
        h = dict(self.android_headers)
        h["Device-Id"] = self._clean(device_id)
        return self._sanitize_headers(h)

    async def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        s = await self._session_get()
        url = f"{self.base_url}{self._clean(path)}"
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

    async def _post_form_json(self, path: str, form: dict[str, str]) -> Any:
        s = await self._session_get()
        url = f"{self.base_url}{self._clean(path)}"
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

    async def _post_json(self, path: str, payload: dict[str, Any]) -> Any:
        s = await self._session_get()
        url = f"{self.base_url}{self._clean(path)}"
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

    # -------------------- public API calls --------------------

    async def mobile_login(
        self, email: str, password: str, device_id: str
    ) -> tuple[str, str | None, Any, Any]:
        s = await self._session_get()
        url = f"{self.base_url}/v2/login/mobile"
        payload: dict[str, Any] = {
            "email": self._clean(email),
            "password": self._clean(password),
            "device_id": self._clean(device_id),
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
            token = self._clean(data.get("token"))
            if not token:
                raise EngieHTTPError(f"LOGIN: token missing in response: {j}")
            refresh_token = self._clean(data.get("refresh_token"))
            exp = data.get("exp")
            refresh_epoch = data.get("refresh_token_expiration_date")
            return token, refresh_token, exp, refresh_epoch

    async def app_status_ok(self) -> bool:
        """Ping simplu pentru a verifica sesiunea/tokenul."""
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

    async def get_index(
        self,
        poc_number: str,
        division: str | None = None,
        pa: str | None = None,
        installation_number: str | None = None,
    ) -> Any:
        """GET /v1/index/{POC}?division=...&pa=...&installation_number=..."""
        params: dict[str, str] = {}
        if self._clean(division):
            params["division"] = self._clean(division)
        if self._clean(pa):
            params["pa"] = self._clean(pa)
        if self._clean(installation_number):
            params["installation_number"] = self._clean(installation_number)
        return await self._get(f"/v1/index/{self._clean(poc_number)}", params=params)

    async def get_balance(self, contract_account: str) -> Any:
        ca = self._clean(contract_account)
        try:
            return await self._post_form_json("/v1/widgets/ballance", {"contract_account[]": ca})
        except EngieHTTPError:
            return await self._post_form_json("/v1/widgets/ballance", {"contract_account": ca})

    async def get_invoices_details(self, contract_account: str) -> Any:
        ca = self._clean(contract_account)
        try:
            return await self._post_form_json(
                "/v1/invoices/ballance-details", {"contract_account[]": ca}
            )
        except EngieHTTPError:
            return await self._post_form_json(
                "/v1/invoices/ballance-details", {"contract_account": ca}
            )

    async def get_consumption(
        self, poc_number: str, start_date: str, end_date: str, pa: str | None = None
    ) -> Any:
        """GET /v1/index/consumption/{POC}?startDate=YYYY-MM-DD&endDate=YYYY-MM-DD&pa=PA"""
        params: dict[str, Any] = {
            "startDate": self._clean(start_date),
            "endDate": self._clean(end_date),
        }
        if self._clean(pa):
            params["pa"] = self._clean(pa)
        return await self._get(f"/v1/index/consumption/{self._clean(poc_number)}", params=params)

    async def get_index_history_post(
        self, autocit: str, poc_number: str, division: str, start_date: str
    ) -> Any:
        """POST /v1/index/history with JSON body."""
        payload = {
            "autocit": self._clean(autocit),
            "poc_number": self._clean(poc_number),
            "division": self._clean(division),
            "start_date": self._clean(start_date),
        }
        return await self._post_json("/v1/index/history", payload)

    async def get_invoices_history(
        self, poc_number: str, start_date: str, end_date: str, pa: str | None = None
    ) -> Any:
        """GET /v1/invoices/history-only/{POC}?startDate=YYYY-MM-DD&endDate=YYYY-MM-DD&pa=PA"""
        params: dict[str, Any] = {
            "startDate": self._clean(start_date),
            "endDate": self._clean(end_date),
        }
        if self._clean(pa):
            params["pa"] = self._clean(pa)
        return await self._get(
            f"/v1/invoices/history-only/{self._clean(poc_number)}", params=params
        )
