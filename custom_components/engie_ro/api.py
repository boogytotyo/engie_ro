from __future__ import annotations

import logging
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant

from .const import USER_AGENT

_LOGGER = logging.getLogger(__name__)


class EngieHTTPError(Exception):
    pass


def _headers(auth: str | None = None) -> dict[str, str]:
    h = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if auth:
        h["Authorization"] = f"Bearer {auth}"
    return h


class EngieClient:
    """Client minimal; completează endpoint-urile reale Engie aici."""

    def __init__(self, hass: HomeAssistant, cfg: dict[str, Any]) -> None:
        self._hass = hass
        self._email: str | None = cfg.get("email")
        self._password: str | None = cfg.get("password")
        self._token: str | None = cfg.get("token")
        self._session: aiohttp.ClientSession | None = None

    async def _session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def ensure_login(self) -> None:
        """Dacă ai token, îl folosești; altfel fă login și setează self._token."""
        if self._token:
            return
        # TODO: login real – la nevoie
        # ridică eroare explicită dacă nu există credențiale
        raise EngieHTTPError("Lipsesc credențialele/token pentru autentificare")

    # ——— Endpoints – înlocuiește corpul cu call-urile reale către Engie ———

    async def get_user_details(self) -> dict[str, Any]:
        """Returnează: email, nume, telefon, adresa, PA/POC, etc."""
        return {}

    async def get_invoices(self) -> dict[str, Any]:
        """Returnează un payload cu facturi ('Invoices' list) – fiecare element are sumă și dată."""
        return {"Invoices": []}

    async def get_unpaid_invoices(self) -> dict[str, Any]:
        """Returnează facturile neplătite: 'Invoices' list cu sume/date."""
        return {"Invoices": []}

    async def get_index_window(self) -> dict[str, Any]:
        """Returnează datele despre fereastra de transmitere index + ultimul index."""
        return {
            "in_window": False,
            "start": None,
            "end": None,
            "allow_submit": False,
            "last_index": None,
        }

    async def get_index_history(self) -> dict[str, Any]:
        """Returnează un payload cu istoricul indexului (ultimele luni)."""
        return {"History": []}
