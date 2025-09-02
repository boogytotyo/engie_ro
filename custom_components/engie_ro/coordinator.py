from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from aiohttp import ClientSession
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EngieApiClient
from .const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    AuthError,
    TemporaryApiError,
)
from .mapping import normalize_billing_history, normalize_current_index, normalize_overview

_LOGGER = logging.getLogger(__name__)


class EngieCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        session: ClientSession,
        api: EngieApiClient,
        update_interval: timedelta,
    ):
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_coordinator",
            update_interval=update_interval or timedelta(seconds=DEFAULT_UPDATE_INTERVAL),
            config_entry=entry,  # 👈 important pentru async_config_entry_first_refresh
        )
        self.entry = entry
        self.api = api
        self.session = session


    async def _async_update_data(self) -> dict[str, Any]:
        try:
            overview_raw = await self.api.fetch_account_overview()
            overview = normalize_overview(overview_raw)

            pa = overview.get("pa") or "PA_UNKNOWN"
            poc = overview.get("poc") or "POC_UNKNOWN"
            division = overview.get("division") or "gaz"

            current_index_raw = await self.api.fetch_current_index(poc, division)
            current_index = normalize_current_index(current_index_raw)

            history_raw = await self.api.fetch_billing_history(
                pa, division, start_date="2022-01-01"
            )
            billing_history = normalize_billing_history(history_raw)

            return {
                "overview": overview,
                "current_index": current_index,
                "billing_history": billing_history,
            }

        except AuthError as exc:
            raise ConfigEntryAuthFailed from exc
        except TemporaryApiError as exc:
            raise UpdateFailed(f"Temporary API error: {exc.status}") from exc
        except Exception as exc:  # noqa: BLE001
            raise UpdateFailed(str(exc)) from exc


async def create_coordinator(
    hass: HomeAssistant, entry: ConfigEntry, update_interval: timedelta
) -> EngieCoordinator:
    session = async_get_clientsession(hass)
    api = EngieApiClient(session=session)

    file_token = await EngieApiClient.load_token(hass)

    email = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]
    if not file_token:
        token = await api.login(email, password)
        await EngieApiClient.save_token(hass, token, meta={"source": "login"})
    else:
        api.set_runtime_token(file_token)

    return EngieCoordinator(hass, entry, session, api, update_interval)
