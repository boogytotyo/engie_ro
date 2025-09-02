from __future__ import annotations
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import voluptuous as vol
import uuid
from .const import (
    DOMAIN, CONF_BASE_URL, CONF_USERNAME, CONF_PASSWORD, CONF_TOKEN_FILE, CONF_DEVICE_ID,
    CONF_AUTH_MODE, AUTH_MODE_MOBILE, AUTH_MODE_BEARER, CONF_BEARER_TOKEN,
    DEFAULT_BASE_URL, DEFAULT_TOKEN_FILE,
)

AUTH_MODES = [AUTH_MODE_MOBILE, AUTH_MODE_BEARER]


def _map_engie_error(exc) -> str:
    code = getattr(exc, "status", None) or getattr(exc, "status_code", None)
    if code == 401:
        return "invalid_auth"
    if code in (403,):
        return "invalid_auth"
    if code in (429,):
        return "rate_limited"
    if code in (500, 502, 503, 504):
        return "server_error"
    if code in (408,):
        return "timeout"
    return "cannot_connect"


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            user_input[CONF_DEVICE_ID] = user_input.get(CONF_DEVICE_ID) or "ha-" + uuid.uuid4().hex[:12]
            return self.async_create_entry(title="Engie România", data=user_input)

        schema = vol.Schema({
            vol.Required(CONF_AUTH_MODE, default=AUTH_MODE_MOBILE): vol.In(AUTH_MODES),
            vol.Optional(CONF_USERNAME): str,
            vol.Optional(CONF_PASSWORD): str,
            vol.Optional(CONF_BEARER_TOKEN): str,
            vol.Optional(CONF_TOKEN_FILE, default=DEFAULT_TOKEN_FILE): str,
            vol.Optional(CONF_BASE_URL, default=DEFAULT_BASE_URL): str,
        })
        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return OptionsFlowHandler(config_entry)

class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self.entry = entry

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        if user_input is not None:
            new_data = dict(self.entry.data)
            for key in (CONF_AUTH_MODE, CONF_USERNAME, CONF_PASSWORD, CONF_BEARER_TOKEN, CONF_TOKEN_FILE, CONF_BASE_URL):
                if key in user_input and user_input[key] is not None:
                    new_data[key] = user_input[key]
            self.hass.config_entries.async_update_entry(self.entry, data=new_data, options={})
            return self.async_create_entry(title="", data={})

        d = self.entry.data
        schema = vol.Schema({
            vol.Required(CONF_AUTH_MODE, default=d.get(CONF_AUTH_MODE) or AUTH_MODE_MOBILE): vol.In(AUTH_MODES),
            vol.Optional(CONF_USERNAME, default=d.get(CONF_USERNAME, "")): str,
            vol.Optional(CONF_PASSWORD, default=d.get(CONF_PASSWORD, "")): str,
            vol.Optional(CONF_BEARER_TOKEN, default=d.get(CONF_BEARER_TOKEN, "")): str,
            vol.Optional(CONF_TOKEN_FILE, default=d.get(CONF_TOKEN_FILE, DEFAULT_TOKEN_FILE)): str,
            vol.Optional(CONF_BASE_URL, default=d.get(CONF_BASE_URL, DEFAULT_BASE_URL)): str,
        })
        return self.async_show_form(step_id="init", data_schema=schema)
