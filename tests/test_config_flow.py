from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.engie_ro.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)


@pytest.mark.parametrize("login_ok", [True, False])
async def test_config_flow_user_step(hass: HomeAssistant, login_ok: bool):
    email = "u@x.y"
    password = "secret"

    # Evităm sesiuni reale + setup real al entry-ului
    with patch(
        "homeassistant.helpers.aiohttp_client.async_get_clientsession",
        return_value=object(),
    ), patch(
        "custom_components.engie_ro.config_flow.EngieApiClient.login",
        new=AsyncMock(),
    ) as m_login, patch(
        "custom_components.engie_ro.config_flow.EngieApiClient.save_token",
        new=AsyncMock(),
    ), patch(
        # Nu lăsăm HA să pornească platformele reale după create_entry
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        new=AsyncMock(),
    ), patch(
        # Nici coordinatorul nu vrem să fie creat în testul acesta
        "custom_components.engie_ro.__init__.create_coordinator",
        new=AsyncMock(),
    ):
        form_result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        assert form_result["type"] == "form"

        if login_ok:
            m_login.return_value = "TOK"
        else:
            m_login.side_effect = Exception("Invalid credentials")

        user_input = {
            CONF_EMAIL: email,
            CONF_PASSWORD: password,
            CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL,
        }
        result = await hass.config_entries.flow.async_configure(
            form_result["flow_id"], user_input=user_input
        )

    if login_ok:
        assert result["type"] == "create_entry"
        assert result["data"][CONF_EMAIL] == email
        assert result["data"][CONF_PASSWORD] == password
        assert result["options"][CONF_UPDATE_INTERVAL] == DEFAULT_UPDATE_INTERVAL
    else:
        assert result["type"] == "form"
        assert result["errors"]["base"] in {"invalid_auth", "unknown"}


async def test_options_flow(hass: HomeAssistant):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Engie (u@x.y)",
        data={CONF_EMAIL: "u@x.y", CONF_PASSWORD: "p"},
        options={CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL},
        unique_id="engie_ro:test",
        version=1,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == "form"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_UPDATE_INTERVAL: 777}
    )
    assert result2["type"] == "create_entry"
    assert result2["data"][CONF_UPDATE_INTERVAL] == 777
