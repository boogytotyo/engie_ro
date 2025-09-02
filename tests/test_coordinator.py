from __future__ import annotations
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from datetime import timedelta

from custom_components.engie_ro.coordinator import create_coordinator
from custom_components.engie_ro.const import DOMAIN, CONF_EMAIL, CONF_PASSWORD
from homeassistant.config_entries import ConfigEntry

@pytest.fixture
def entry(hass: HomeAssistant):
    e = ConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Engie (u@x.y)",
        data={CONF_EMAIL:"u@x.y", CONF_PASSWORD:"p"},
        source="user",
        entry_id="test",
    )
    return e

async def test_coordinator_happy_path(hass: HomeAssistant, entry: ConfigEntry):
    with patch("custom_components.engie_ro.api.EngieApiClient.load_token", new=AsyncMock(return_value="TOK")),          patch("custom_components.engie_ro.api.EngieApiClient.save_token", new=AsyncMock()),          patch("custom_components.engie_ro.api.EngieApiClient.set_runtime_token"),          patch("custom_components.engie_ro.api.EngieApiClient.fetch_account_overview", new=AsyncMock(return_value={
            "contract_account":"123", "POC":"5001", "Division":"gaz", "CustomerEmail":"u@x.y"
         })),          patch("custom_components.engie_ro.api.EngieApiClient.fetch_current_index", new=AsyncMock(return_value={
            "reading":"345.1","Unit":"kWh","time":"2025-09-01T10:00:00"
         })),          patch("custom_components.engie_ro.api.EngieApiClient.fetch_billing_history", new=AsyncMock(return_value={
            "data":[{"invoice_id":"A1","InvoiceDate":"2025-08-01","DueDate":"2025-08-20","value":100,"Currency":"RON","Status":"PAID"}]
         })):
        coord = await create_coordinator(hass, entry, timedelta(seconds=10))
        await coord.async_config_entry_first_refresh()

    assert coord.data["overview"]["pa"] == "123"
    assert coord.data["overview"]["poc"] == "5001"
    assert coord.data["current_index"]["value"] == 345.1
    assert coord.data["billing_history"]["last"]["id"] == "A1"

async def test_coordinator_auth_error_triggers_reauth(hass: HomeAssistant, entry: ConfigEntry):
    from custom_components.engie_ro.const import AuthError
    with patch("custom_components.engie_ro.api.EngieApiClient.load_token", new=AsyncMock(return_value="TOK")),          patch("custom_components.engie_ro.api.EngieApiClient.fetch_account_overview", new=AsyncMock(side_effect=AuthError("401"))):
        coord = await create_coordinator(hass, entry, timedelta(seconds=10))
        with pytest.raises(Exception):
            await coord._async_update_data()
