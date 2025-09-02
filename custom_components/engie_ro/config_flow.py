from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries

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


class EngieConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        schema = vol.Schema(
            {
                vol.Optional(CONF_BASE_URL, default=DEFAULT_BASE_URL): str,
                vol.Optional(CONF_AUTH_MODE, default=AUTH_MODE_MOBILE): vol.In(
                    [AUTH_MODE_MOBILE, AUTH_MODE_BEARER]
                ),
                vol.Optional(CONF_USERNAME, default=""): str,
                vol.Optional(CONF_PASSWORD, default=""): str,
                vol.Optional(CONF_DEVICE_ID, default=""): str,
                vol.Optional(CONF_BEARER_TOKEN, default=""): str,
                vol.Optional(CONF_TOKEN_FILE, default=DEFAULT_TOKEN_FILE): str,
            }
        )

        if user_input is not None:
            # Minimal validation here; real auth happens in coordinator
            auth_mode = (user_input.get(CONF_AUTH_MODE) or AUTH_MODE_MOBILE).strip()

            if auth_mode == AUTH_MODE_MOBILE:
                if not user_input.get(CONF_USERNAME) or not user_input.get(CONF_PASSWORD):
                    errors["base"] = "missing_credentials"
            elif auth_mode == AUTH_MODE_BEARER:
                if not user_input.get(CONF_BEARER_TOKEN):
                    errors["base"] = "missing_bearer"
            else:
                errors["base"] = "invalid_auth_mode"

            if not errors:
                return self.async_create_entry(title="Engie România", data=user_input)

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
