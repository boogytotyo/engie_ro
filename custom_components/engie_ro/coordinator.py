from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EngieClient
from .const import UPDATE_INTERVAL_MINUTES

_LOGGER = logging.getLogger(__name__)


class EngieDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator: face login, apoi adună toate datele într-un singur dict."""

    def __init__(self, hass: HomeAssistant, cfg: dict[str, Any]) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="engie_ro",
            update_interval=timedelta(minutes=UPDATE_INTERVAL_MINUTES),
        )
        self._client = EngieClient(hass, cfg)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch asincron; SENZORII citesc exclusiv din self.data."""
        try:
            await self._client.ensure_login()

            # ——— AICI apelezi API-urile reale ———
            # exemplu de chei: adaptează la Engie
            user_details = await self._client.get_user_details()
            invoices = await self._client.get_invoices()
            unpaid = await self._client.get_unpaid_invoices()
            index_window = (
                await self._client.get_index_window()
            )  # perioada și posibilitatea raportării
            index_history = (
                await self._client.get_index_history()
            )  # listă cu (start, end, index, consum)

            return {
                "user_details": user_details,
                "invoices": invoices,
                "unpaid": unpaid,
                "index_window": index_window,
                "index_history": index_history,
            }
        except Exception as err:  # pragma: no cover – defensiv
            raise UpdateFailed(str(err)) from err
