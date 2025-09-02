from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries

from .const import CONF_EMAIL, CONF_PASSWORD, CONF_TOKEN, DOMAIN


class EngieConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            # validare minimă
            if not user_input.get(CONF_TOKEN) and (
                not user_input.get(CONF_EMAIL) or not user_input.get(CONF_PASSWORD)
            ):
                errors["base"] = "invalid_auth"
            else:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Engie România", data=user_input)

        schema = vol.Schema(
            {
                vol.Optional(CONF_EMAIL): str,
                vol.Optional(CONF_PASSWORD): str,
                vol.Optional(CONF_TOKEN): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
