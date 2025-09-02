from __future__ import annotations
from typing import Any, Dict
import voluptuous as vol
from homeassistant import config_entries
from .const import (
    DOMAIN,
    CONF_BASE_URL,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_TOKEN_FILE,
    CONF_DEVICE_ID,
    CONF_AUTH_MODE,
    CONF_BEARER_TOKEN,
    DEFAULT_BASE_URL,
    DEFAULT_TOKEN_FILE,
    AUTH_MODE_MOBILE,
    AUTH_MODE_BEARER,
)


class EngieConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: Dict[str, Any] | None = None):
        errors: Dict[str, str] = {}

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
            # Normalize values (strip)
            normalized = {
                CONF_BASE_URL: (user_input.get(CONF_BASE_URL) or DEFAULT_BASE_URL).strip(),
                CONF_AUTH_MODE: (user_input.get(CONF_AUTH_MODE) or AUTH_MODE_MOBILE).strip(),
                CONF_USERNAME: (user_input.get(CONF_USERNAME) or "").strip(),
                CONF_PASSWORD: (user_input.get(CONF_PASSWORD) or "").strip(),
                CONF_DEVICE_ID: (user_input.get(CONF_DEVICE_ID) or "").strip(),
                CONF_BEARER_TOKEN: (user_input.get(CONF_BEARER_TOKEN) or "").strip(),
                CONF_TOKEN_FILE: (user_input.get(CONF_TOKEN_FILE) or DEFAULT_TOKEN_FILE).strip(),
            }

            auth_mode = normalized[CONF_AUTH_MODE]

            if auth_mode == AUTH_MODE_MOBILE:
                if not normalized[CONF_USERNAME] or not normalized[CONF_PASSWORD]:
                    errors["base"] = "missing_credentials"
            elif auth_mode == AUTH_MODE_BEARER:
                if not normalized[CONF_BEARER_TOKEN]:
                    errors["base"] = "missing_bearer"
            else:
                errors["base"] = "invalid_auth_mode"

            if not errors:
                return self.async_create_entry(title="Engie România", data=normalized)

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)