from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path

from .api import EngieClient, EngieHTTPError, EngieUnauthorized
from .const import AUTH_MODE_MOBILE, DEFAULT_TOKEN_FILE

_LOGGER = logging.getLogger(__name__)

# Reîmprospătează token-ul cu 5 minute înainte de expirare
_REFRESH_MARGIN_SEC = 300


def _exp_epoch_from_response(exp_raw: object, now: float) -> float:
    """Determină timestamp-ul Unix de expirare din câmpul 'exp' al API-ului.

    API-ul poate returna:
    - Un timestamp Unix epoch (ex. 1774026000) — valoare mare (> 1_000_000_000)
    - Numărul de secunde până la expirare (ex. 3600) — valoare mică
    Dacă câmpul lipsește, presupunem 1 oră.
    """
    try:
        val = int(str(exp_raw))
    except (TypeError, ValueError):
        return now + 3600

    # Dacă valoarea e mai mare de 10^9 e deja un epoch Unix
    if val > 1_000_000_000:
        return float(val)

    # Altfel e numărul de secunde până la expirare
    return now + val


class EngieAuthManager:
    def __init__(
        self,
        client: EngieClient,
        username: str | None,
        password: str | None,
        token_file: str | None,
        device_id: str,
        auth_mode: str,
        bearer_token: str | None,
    ):
        self.client = client
        self.username = username
        self.password = password
        self.token_path = Path(token_file or DEFAULT_TOKEN_FILE)
        self.device_id = device_id
        self.auth_mode = auth_mode
        self.initial_bearer = (bearer_token or "").strip()
        self._exp_epoch: float | None = None
        self._lock = asyncio.Lock()

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
            await asyncio.to_thread(
                tmp.write_text,
                json.dumps(bundle, ensure_ascii=False, indent=0),
                encoding="utf-8",
            )
            os.replace(tmp, self.token_path)
        except Exception as e:
            _LOGGER.warning("Cannot write token to file %s: %s", self.token_path, e)

    async def _do_login(self) -> str:
        """Efectuează login complet și salvează bundle-ul în fișier."""
        if not self.username or not self.password:
            raise EngieHTTPError("Lipsesc username/password pentru mobile login.")
        _LOGGER.debug("Engie: efectuez login pentru %s", self.username)
        token, refresh_token, exp_raw, refresh_epoch = await self.client.mobile_login(
            self.username, self.password, self.device_id
        )
        now = time.time()
        exp_epoch = _exp_epoch_from_response(exp_raw, now)
        self._exp_epoch = exp_epoch
        bundle = {
            "token": token,
            "refresh_token": refresh_token,
            "exp_epoch": exp_epoch,
            "refresh_token_expiration_date": refresh_epoch,
        }
        await self._write_token_to_file(bundle)
        self.client.token = token
        _LOGGER.debug(
            "Engie: token obținut, expiră la epoch %.0f (peste %.0f minute)",
            exp_epoch,
            (exp_epoch - now) / 60,
        )
        return token

    def _token_needs_refresh(self, exp_epoch: float | None) -> bool:
        """Returnează True dacă token-ul expiră în mai puțin de _REFRESH_MARGIN_SEC."""
        if exp_epoch is None:
            return True
        return time.time() >= exp_epoch - _REFRESH_MARGIN_SEC

    async def ensure_valid_token(self) -> str:
        """Asigură că clientul are un token valid înainte de orice apel API.

        Folosește un lock pentru a evita login-uri paralele în cazul mai multor
        update-uri concurente.
        """
        if self.initial_bearer:
            self.client.token = self.initial_bearer
            return self.initial_bearer

        async with self._lock:
            # Re-citim fișierul de fiecare dată — alt proces/restart ar fi putut
            # actualiza token-ul între timp
            bundle = await self._read_token_from_file()
            if bundle:
                tok = bundle.get("token", "")
                exp_epoch = bundle.get("exp_epoch")
                try:
                    exp_epoch = float(exp_epoch) if exp_epoch is not None else None
                except (TypeError, ValueError):
                    exp_epoch = None

                if tok and not self._token_needs_refresh(exp_epoch):
                    # Token valid, folosim direct
                    self.client.token = tok
                    self._exp_epoch = exp_epoch
                    return tok

                if tok and self.auth_mode == AUTH_MODE_MOBILE:
                    # Token aproape expirat — reînnoim proactiv
                    _LOGGER.debug("Engie: token expiră curând, reînnoiesc proactiv.")
                    return await self._do_login()

            # Nu avem token sau a expirat complet
            if self.auth_mode == AUTH_MODE_MOBILE:
                return await self._do_login()

            raise EngieUnauthorized(
                "Bearer token lipsă sau invalid. Furnizați un token valid sau treceți la mobile login."
            )

    async def refresh_after_401(self) -> str:
        """Apelat de coordinator după un 401 neașteptat în timpul unui apel API.

        Forțează re-login indiferent de starea curentă a token-ului.
        """
        if self.auth_mode != AUTH_MODE_MOBILE:
            raise EngieUnauthorized(
                "Bearer token expirat/invalid. Actualizați token-ul din Opțiuni."
            )
        async with self._lock:
            _LOGGER.warning("Engie: 401 neașteptat — forțez re-login.")
            return await self._do_login()