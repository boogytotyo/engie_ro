from __future__ import annotations
import logging, os, json, time, asyncio
from pathlib import Path
from .const import DEFAULT_TOKEN_FILE, AUTH_MODE_MOBILE
from .api import EngieClient, EngieHTTPError, EngieUnauthorized

_LOGGER = logging.getLogger(__name__)

class EngieAuthManager:
    def __init__(self, client: EngieClient, username: str | None, password: str | None, token_file: str | None, device_id: str, auth_mode: str, bearer_token: str | None):
        self.client = client
        self.username = username
        self.password = password
        self.token_path = Path(token_file or DEFAULT_TOKEN_FILE)
        self.device_id = device_id
        self.auth_mode = auth_mode
        self.initial_bearer = (bearer_token or "").strip()
        self._exp_epoch: float | None = None

    async def _read_token_from_file(self) -> dict | None:
        try:
            if not self.token_path.exists():
                return None
            txt = await asyncio.to_thread(self.token_path.read_text, encoding="utf-8")
            txt = txt.strip()
            if not txt:
                return None
            if txt.startswith("{"):
                return json.loads(txt)
            return {"token": txt}
        except Exception as e:
            _LOGGER.debug("Cannot read token file: %s", e)
            return None

    async def _write_token_to_file(self, bundle: dict) -> None:
        try:
            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.token_path.with_suffix(self.token_path.suffix + ".tmp")
            await asyncio.to_thread(tmp.write_text, json.dumps(bundle, ensure_ascii=False, indent=0), encoding="utf-8")
            os.replace(tmp, self.token_path)
        except Exception as e:
            _LOGGER.warning("Cannot write token to file %s: %s", self.token_path, e)

    async def _login_mobile(self) -> str:
        if not self.username or not self.password:
            raise EngieHTTPError("Missing username/password for mobile login")
        token, refresh_token, exp_sec, refresh_epoch = await self.client.mobile_login(self.username, self.password, self.device_id)
        now = time.time()
        exp_epoch = now + (int(exp_sec) if exp_sec else 3600)
        self._exp_epoch = exp_epoch
        bundle = {"token": token, "refresh_token": refresh_token, "exp": exp_sec, "exp_epoch": exp_epoch, "refresh_token_expiration_date": refresh_epoch}
        await self._write_token_to_file(bundle)
        self.client.token = token
        return token

    async def ensure_valid_token(self) -> str:
        if self.initial_bearer:
            self.client.token = self.initial_bearer
            return self.initial_bearer

        b = await self._read_token_from_file()
        if b:
            tok = b.get("token")
            if tok:
                self.client.token = tok
                self._exp_epoch = b.get("exp_epoch")
                if isinstance(self._exp_epoch, (int, float)) and time.time() > float(self._exp_epoch) - 120:
                    if self.auth_mode == AUTH_MODE_MOBILE:
                        return await self._login_mobile()
                try:
                    await self.client.app_status_ok()
                    return tok
                except EngieUnauthorized:
                    pass
                except Exception:
                    return tok

        if self.auth_mode == AUTH_MODE_MOBILE:
            return await self._login_mobile()
        else:
            raise EngieUnauthorized("Bearer token missing/invalid. Provide a valid token or switch to mobile login.")

    async def refresh_after_401(self) -> str:
        if self.auth_mode == AUTH_MODE_MOBILE:
            return await self._login_mobile()
        raise EngieUnauthorized("Bearer token expired/invalid. Update the token in Options.")
