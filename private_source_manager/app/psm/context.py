"""Application scoped objects, keyed so handlers in any module can reach them."""

from __future__ import annotations

from aiohttp import web

from .config import Settings
from .credentials import CredentialStore
from .db import Database
from .gitops import Git
from .hass import HomeAssistant
from .hosts import Hosts
from .installer import Installer
from .repos import RepositoryStore
from .vault import Vault

SETTINGS: web.AppKey[Settings] = web.AppKey("settings", Settings)
DB: web.AppKey[Database] = web.AppKey("db", Database)
VAULT: web.AppKey[Vault] = web.AppKey("vault", Vault)
CREDENTIALS: web.AppKey[CredentialStore] = web.AppKey("credentials", CredentialStore)
GIT: web.AppKey[Git] = web.AppKey("git", Git)
HASS: web.AppKey[HomeAssistant] = web.AppKey("hass", HomeAssistant)
HOSTS: web.AppKey[Hosts] = web.AppKey("hosts", Hosts)
INSTALLER: web.AppKey[Installer] = web.AppKey("installer", Installer)
REPOS: web.AppKey[RepositoryStore] = web.AppKey("repos", RepositoryStore)
