from __future__ import annotations

import uuid

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    AUTH_MODE_BEARER,
    AUTH_MODE_MOBILE,
    CONF_AUTH_MODE,
    CONF_BASE_URL,
    CONF_BEARER_TOKEN,
    CONF_DEVICE_ID,
    CONF_PASSWORD,
    CONF_TOKEN_FILE,
    CONF_USERNAME,
    DEFAULT_BASE_URL,
    DEFAULT_TOKEN_FILE,
    DOMAIN,
)

AUTH_MODES = [AUTH_MODE_MOBILE, AUTH_MODE_BEARER]


def _unique_token_file(username: str = "") -> str:
    """Return a unique token file path. Always guaranteed to be unique."""
    if username:
        safe = (
            username.strip().lower()
            .replace("@", "_at_")
            .replace(".", "_")
            .replace("+", "_")
            .replace(" ", "_")
        )
        return f"/config/engie_token_{safe}.txt"
    # No username (bearer mode) — use a short random suffix
    return f"/config/engie_token_{uuid.uuid4().hex[:8]}.txt"


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            auth_mode = user_input.get(CONF_AUTH_MODE) or AUTH_MODE_MOBILE
            username = (user_input.get(CONF_USERNAME) or "").strip().lower()
            token_file = (user_input.get(CONF_TOKEN_FILE) or "").strip()

            # Unique ID = username for mobile, or a uuid for bearer
            unique_basis = username if username else uuid.uuid4().hex
            await self.async_set_unique_id(unique_basis)
            self._abort_if_unique_id_configured()

            # Always assign a unique token file — override default or empty values
            if not token_file or token_file == DEFAULT_TOKEN_FILE:
                token_file = _unique_token_file(username)
            user_input[CONF_TOKEN_FILE] = token_file

            user_input[CONF_DEVICE_ID] = (
                user_input.get(CONF_DEVICE_ID) or "ha-" + uuid.uuid4().hex[:12]
            )
            title = (
                f"Engie România ({username})" if username
                else "Engie România (bearer)"
            )
            return self.async_create_entry(title=title, data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_AUTH_MODE, default=AUTH_MODE_MOBILE): vol.In(AUTH_MODES),
                vol.Optional(CONF_USERNAME): str,
                vol.Optional(CONF_PASSWORD): str,
                vol.Optional(CONF_BEARER_TOKEN): str,
                vol.Optional(CONF_TOKEN_FILE, default=DEFAULT_TOKEN_FILE): str,
                vol.Optional(CONF_BASE_URL, default=DEFAULT_BASE_URL): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

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
            for key in (
                CONF_AUTH_MODE,
                CONF_USERNAME,
                CONF_PASSWORD,
                CONF_BEARER_TOKEN,
                CONF_TOKEN_FILE,
                CONF_BASE_URL,
            ):
                if key in user_input and user_input[key] is not None:
                    new_data[key] = user_input[key]
            self.hass.config_entries.async_update_entry(self.entry, data=new_data, options={})
            return self.async_create_entry(title="", data={})

        d = self.entry.data
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_AUTH_MODE, default=d.get(CONF_AUTH_MODE) or AUTH_MODE_MOBILE
                ): vol.In(AUTH_MODES),
                vol.Optional(CONF_USERNAME, default=d.get(CONF_USERNAME, "")): str,
                vol.Optional(CONF_PASSWORD, default=d.get(CONF_PASSWORD, "")): str,
                vol.Optional(CONF_BEARER_TOKEN, default=d.get(CONF_BEARER_TOKEN, "")): str,
                vol.Optional(
                    CONF_TOKEN_FILE,
                    default=d.get(CONF_TOKEN_FILE, DEFAULT_TOKEN_FILE),
                ): str,
                vol.Optional(CONF_BASE_URL, default=d.get(CONF_BASE_URL, DEFAULT_BASE_URL)): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
