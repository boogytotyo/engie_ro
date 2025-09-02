from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "engie_ro"

CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_TOKEN = "token"  # opțional, pentru mod avansat (bearer)
CONF_LANGUAGE = "language"

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.UPDATE]

# interval default; poate fi ajustat din coordinator
UPDATE_INTERVAL_MINUTES = 30

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
)

ATTRIBUTION = "Data: Engie România"
