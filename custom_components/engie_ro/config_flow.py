from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EngieApiClient
from .const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    MIN_UPDATE_INTERVAL,
)

STEP_USER = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): int,
    }
)


class EngieConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=STEP_USER)

        errors: dict[str, str] = {}
        email = user_input[CONF_EMAIL].strip()
        password = user_input[CONF_PASSWORD]
        update_interval = max(int(user_input[CONF_UPDATE_INTERVAL]), MIN_UPDATE_INTERVAL)

        session = async_get_clientsession(self.hass)
        api = EngieApiClient(session)
        try:
            token = await api.login(email, password)
            await EngieApiClient.save_token(self.hass, token, meta={"source": "config_flow"})
        except Exception as exc:  # noqa: BLE001
            msg = str(exc).lower()
            if "invalid" in msg or "credential" in msg or "401" in msg:
                errors["base"] = "invalid_auth"
            elif "timeout" in msg or "temporary" in msg:
                errors["base"] = "cannot_connect"
            else:
                errors["base"] = "unknown"
            return self.async_show_form(step_id="user", data_schema=STEP_USER, errors=errors)

        await self.async_set_unique_id(f"{DOMAIN}:{email.lower()}")
        self._abort_if_unique_id_configured()

        data = {
            CONF_EMAIL: email,
            CONF_PASSWORD: password,
        }
        options = {CONF_UPDATE_INTERVAL: update_interval}
        return self.async_create_entry(title=f"Engie ({email})", data=data, options=options)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return EngieOptionsFlow(config_entry)


class EngieOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        if user_input is not None:
            update_interval = max(int(user_input[CONF_UPDATE_INTERVAL]), MIN_UPDATE_INTERVAL)
            return self.async_create_entry(title="", data={CONF_UPDATE_INTERVAL: update_interval})

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_UPDATE_INTERVAL,
                    default=self.config_entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
                ): int
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
