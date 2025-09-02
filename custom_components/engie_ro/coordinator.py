# ... restul importurilor și clasei ...

    async def _load_token_file(self) -> str | None:
        try:
            with open(self._token_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            return None

    async def _save_token_file(self, token: str) -> None:
        try:
            with open(self._token_file, "w", encoding="utf-8") as f:
                f.write((token or "").strip())
        except Exception as e:
            LOGGER.debug("Could not save token file: %s", e)

    async def _ensure_client(self) -> EngieClient:
        if self._client is None:
            s = await self._session_get()
            token = (self._bearer or (await self._load_token_file()) or "").strip()
            self._client = EngieClient(self._base_url, token=token, session=s)
        return self._client

    async def _login_mobile_if_needed(self) -> None:
        if self._auth_mode != AUTH_MODE_MOBILE:
            return
        token = ((await self._load_token_file()) or "").strip()
        if token:
            return
        auth = EngieMobileAuth(self._base_url, session=await self._session_get())
        token, refresh, exp, refresh_epoch = await auth.login(
            self._username.strip(), self._password.strip(), (self._device_id or "device").strip()
        )
        await auth.close()
        await self._save_token_file(token)
        self._client = EngieClient(self._base_url, token=token, session=await self._session_get())