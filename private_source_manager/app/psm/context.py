"""Application scoped objects, keyed so handlers in any module can reach them."""

from __future__ import annotations

from aiohttp import web

from .config import Settings
from .credentials import CredentialStore
from .db import Database
from .vault import Vault

SETTINGS: web.AppKey[Settings] = web.AppKey("settings", Settings)
DB: web.AppKey[Database] = web.AppKey("db", Database)
VAULT: web.AppKey[Vault] = web.AppKey("vault", Vault)
CREDENTIALS: web.AppKey[CredentialStore] = web.AppKey("credentials", CredentialStore)
