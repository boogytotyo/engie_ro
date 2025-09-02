from __future__ import annotations

import time
from dataclasses import dataclass

from .api import EngieApiClient

AUTH_MODE_MOBILE = "mobile"
AUTH_MODE_WEB = "web"


@dataclass
class TokenBundle:
    token: str
    exp_epoch: float | None = None  # unix epoch seconds


class AuthManager:
    """Lightweight token manager; supports one mode (email/password) here."""

    def __init__(self, client: EngieApiClient, auth_mode: str = AUTH_MODE_MOBILE):
        self.client = client
        self.auth_mode = auth_mode
        self._bundle: TokenBundle | None = None

    @property
    def token(self) -> str | None:
        return self._bundle.token if self._bundle else None

    async def ensure_token(self, email: str, password: str) -> str:
        # If we have a non-expired token, reuse it
        if self._bundle and self._bundle.exp_epoch is not None:
            try:
                expf = float(self._bundle.exp_epoch)
            except (TypeError, ValueError):
                expf = None
            if expf is not None and time.time() < expf - 120:
                return self._bundle.token

        # Refresh/login
        tok = await self.client.login(email, password)
        self._bundle = TokenBundle(token=tok, exp_epoch=None)
        return tok

    def set_bundle(self, token: str, exp_epoch: float | None) -> None:
        self._bundle = TokenBundle(token=token, exp_epoch=exp_epoch)

    def invalidate(self) -> None:
        self._bundle = None
