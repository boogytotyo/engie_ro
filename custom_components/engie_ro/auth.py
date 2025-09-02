from __future__ import annotations

import time
from typing import Any

AUTH_MODE_MOBILE = "mobile"


class AuthManager:
    def __init__(self, client):
        self.client = client
        self._exp_epoch: int | float | None = None
        self.auth_mode = AUTH_MODE_MOBILE

    async def ensure_valid(self) -> None:
        tok = "token_exemplu"
        b: dict[str, Any] = {"exp_epoch": int(time.time()) + 3600}
        self.client.token = tok
        self._exp_epoch = b.get("exp_epoch")

        if isinstance(self._exp_epoch, int | float) and time.time() > float(self._exp_epoch) - 120:
            if self.auth_mode == AUTH_MODE_MOBILE:
                return await self._login_mobile()

    async def _login_mobile(self):
        # logica de login
        return
