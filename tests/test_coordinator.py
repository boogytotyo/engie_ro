from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.engie_ro.const import CONF_EMAIL, CONF_PASSWORD, DOMAIN
from custom_components.engie_ro.coordinator import create_coordinator


@pytest.fixture
def entry(hass: HomeAssistant):
    e = MockConfigEntry(
        domain=DOMAIN,
        title="Engie (u@x.y)",
        data={CONF_EMAIL: "u@x.y", CONF_PASSWORD: "p"},
        options={},
        unique_id="engie_ro:test",
        version=1,
        minor_version=1,
    )
    e.add_to_hass(hass)
    return e


async def test_coordinator_happy_path(hass: HomeAssistant, entry: MockConfigEntry):
    with (
        patch(
            "homeassistant.helpers.aiohttp_client.async_get_clientsession",
            return_value=object(),
        ),
        patch(
            "custom_components.engie_ro.api.EngieApiClient.load_token",
            new=AsyncMock(return_value="TOK"),
        ),
        patch(
            "custom_components.engie_ro.api.EngieApiClient.save_token",
            new=AsyncMock(),
        ),
        patch("custom_components.engie_ro.api.EngieApiClient.set_runtime_token"),
        patch(
            "custom_components.engie_ro.api.EngieApiClient.fetch_account_overview",
            new=AsyncMock(
                return_value={
                    "contract_account": "123",
                    "POC": "5001",
                    "Division": "gaz",
                    "CustomerEmail": "u@x.y",
                }
            ),
        ),
        patch(
            "custom_components.engie_ro.api.EngieApiClient.fetch_current_index",
            new=AsyncMock(
                return_value={
                    "reading": "345.1",
                    "Unit": "kWh",
                    "time": "2025-09-01T10:00:00",
                }
            ),
        ),
        patch(
            "custom_components.engie_ro.api.EngieApiClient.fetch_billing_history",
            new=AsyncMock(
                return_value={
                    "data": [
                        {
                            "invoice_id": "A1",
                            "InvoiceDate": "2025-08-01",
                            "DueDate": "2025-08-20",
                            "value": 100,
                            "Currency": "RON",
                            "Status": "PAID",
                        }
                    ]
                }
            ),
        ),
    ):
    coord = await create_coordinator(hass, entry, timedelta(seconds=10))
    await coord.async_refresh()
    assert coord.last_update_success

    assert coord.data["overview"]["pa"] == "123"
    assert coord.data["overview"]["poc"] == "5001"
    assert coord.data["current_index"]["value"] == 345.1
    assert coord.data["billing_history"]["last"]["id"] == "A1"


async def test_coordinator_auth_error_triggers_reauth(hass: HomeAssistant, entry: MockConfigEntry):
    from custom_components.engie_ro.const import AuthError

    with (
        patch(
            "homeassistant.helpers.aiohttp_client.async_get_clientsession",
            return_value=object(),
        ),
        patch(
            "custom_components.engie_ro.api.EngieApiClient.load_token",
            new=AsyncMock(return_value="TOK"),
        ),
        patch(
            "custom_components.engie_ro.api.EngieApiClient.fetch_account_overview",
            new=AsyncMock(side_effect=AuthError("401")),
        ),
    ):
        coord = await create_coordinator(hass, entry, timedelta(seconds=10))
        with pytest.raises(ConfigEntryAuthFailed):
            await coord._async_update_data()
