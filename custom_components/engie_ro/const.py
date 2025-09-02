from __future__ import annotations

DOMAIN = "engie_ro"
PLATFORMS = ["sensor"]
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_UPDATE_INTERVAL = "update_interval"  # seconds

DEFAULT_UPDATE_INTERVAL = 1800  # 30 min
MIN_UPDATE_INTERVAL = 300  # 5 min guard

TOKEN_STORAGE_FILE = ".storage/engie_ro_token.json"

# Device
MANUFACTURER = "Engie România"
DEVICE_NAME_FMT = "Engie {pa}"  # ex. "Engie 5001888606"

# Keys model intern (normalizează răspunsul API)
KEY_ACCOUNT = "pa"
KEY_POC = "poc"
KEY_DIVISION = "division"


# Erori interne
class AuthError(Exception):
    pass


class TemporaryApiError(Exception):
    def __init__(self, status: int | None = None, message: str | None = None):
        super().__init__(message)
        self.status = status
