from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

_LOGGER = logging.getLogger(__name__)


class EngieDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator pentru integrarea ENGIE.

    TODO: populează _async_update_data() cu request-urile reale către API
    și returnează un dict cu cheile de care ai nevoie în senzori.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="engie_ro",
            update_interval=timedelta(minutes=30),
        )
        # ex.: self.api = EngieClient(...)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch asincron de date. Aruncă UpdateFailed pe erori."""
        try:
            # Exemplu de schelet – înlocuiește cu fetch real:
            # facturi = await self.api.get_invoices()
            # consum = await self.api.get_consum()
            # return {"facturi": facturi, "consum": consum}
            return {}
        except Exception as err:  # pragma: no cover - defensive
            raise UpdateFailed(str(err)) from err
