from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant

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
    form_result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert form_result["type"] == "form"

    with (
        patch(
            "custom_components.engie_ro.config_flow.EngieApiClient.login", new=AsyncMock()
        ) as m_login,
        patch("custom_components.engie_ro.config_flow.EngieApiClient.save_token", new=AsyncMock()),
    ):
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
    entry = config_entries.ConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Engie (u@x.y)",
        data={CONF_EMAIL: "u@x.y", CONF_PASSWORD: "p"},
        options={CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL},
        source="user",
        entry_id="test",
    )
    hass.config_entries._entries.append(entry)  # noqa: SLF001

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == "form"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_UPDATE_INTERVAL: 777}
    )
    assert result2["type"] == "create_entry"
    assert result2["data"][CONF_UPDATE_INTERVAL] == 777
