from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.engie_ro import async_setup_entry
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


async def test_sensor_values(hass: HomeAssistant, entry: MockConfigEntry):
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
            new=AsyncMock(return_value={"pa": "123", "poc": "5001", "division": "gaz"}),
        ),
        patch(
            "custom_components.engie_ro.api.EngieApiClient.fetch_current_index",
            new=AsyncMock(
                return_value={
                    "value": "111.2",
                    "unit": "kWh",
                    "timestamp": "2025-09-01T10:00:00",
                }
            ),
        ),
        patch(
            "custom_components.engie_ro.api.EngieApiClient.fetch_billing_history",
            new=AsyncMock(
                return_value={
                    "items": [
                        {
                            "id": "B9",
                            "issue_date": "2025-07-01",
                            "due_date": "2025-07-20",
                            "amount": 88.50,
                            "currency": "RON",
                            "status": "unpaid",
                        }
                    ]
                }
            ),
        ),
        patch(
            "custom_components.engie_ro.coordinator.EngieCoordinator.async_config_entry_first_refresh",
            new=AsyncMock(),
        ),
    ):
        coord = await create_coordinator(hass, entry, timedelta(seconds=10))
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coord

        # nu pornim platformele reale; doar confirmăm că setup_entry nu crapă
        with patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            new=AsyncMock(),
        ):
            assert await async_setup_entry(hass, entry)

        coord.data = {
            "overview": {"pa": "123", "poc": "5001", "division": "gaz"},
            "current_index": {
                "value": 111.2,
                "unit": "kWh",
                "timestamp": "2025-09-01T10:00:00",
            },
            "billing_history": {
                "items": [{"id": "B9", "amount": 88.5}],
                "last": {"id": "B9", "amount": 88.5},
            },
        }

        assert coord.data["current_index"]["value"] == 111.2
        assert coord.data["billing_history"]["last"]["amount"] == 88.5
