"""aiohttp application wiring."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from pathlib import Path

from aiohttp import web

from . import __version__, api
from .config import Settings
from .content import Targets
from .context import (
    CREDENTIALS,
    DB,
    GIT,
    HASS,
    HOSTS,
    INSTALLER,
    REPOS,
    SETTINGS,
    UPDATER,
    VAULT,
)
from .credentials import CredentialStore
from .db import Database
from .gitops import Git
from .hass import HomeAssistant
from .hosts import Hosts
from .ingress import base_href, peer_guard
from .installer import Installer
from .keystore import LocalKeystore
from .repos import RepositoryStore
from .updater import Updater
from .vault import Vault

_LOGGER = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"

# Rewritten per request because the ingress prefix changes with the session token.
BASE_TAG = '<base href="/">'

AUTO_LOCK_POLL_SECONDS = 30


async def handle_index(request: web.Request) -> web.Response:
    index = STATIC_DIR / "index.html"
    if not index.is_file():
        raise web.HTTPNotFound(text="Frontend bundle is missing")
    html = index.read_text(encoding="utf-8").replace(
        BASE_TAG, f'<base href="{base_href(request)}">', 1
    )
    return web.Response(
        text=html,
        content_type="text/html",
        headers={"Cache-Control": "no-store"},
    )


async def handle_health(_: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "version": __version__})


async def handle_info(request: web.Request) -> web.Response:
    settings = request.app[SETTINGS]
    return web.json_response(
        {
            "version": __version__,
            "dev_mode": settings.dev_mode,
            "ingress_base": base_href(request),
            "supervisor": settings.supervisor_token is not None,
        }
    )


async def _auto_lock_loop(app: web.Application) -> None:
    vault = app[VAULT]
    minutes = app[SETTINGS].auto_lock_minutes
    while True:
        await asyncio.sleep(AUTO_LOCK_POLL_SECONDS)
        vault.maybe_auto_lock(minutes)


async def _lifecycle(app: web.Application) -> AsyncIterator[None]:
    settings = app[SETTINGS]
    settings.ensure_dirs()

    db = Database(settings.db_path)
    vault = Vault(db, LocalKeystore(settings.keystore_dir))
    vault.start()

    targets = Targets(ha_config_dir=settings.ha_config_dir, addons_dir=settings.addons_dir)
    credentials = CredentialStore(db, vault)
    git = Git(settings.cache_dir, settings.known_hosts_path)
    hass = HomeAssistant(settings.supervisor_token)
    hosts = Hosts()
    installer = Installer(db, targets)

    app[DB] = db
    app[VAULT] = vault
    app[CREDENTIALS] = credentials
    app[GIT] = git
    app[HASS] = hass
    app[INSTALLER] = installer
    repos = RepositoryStore(db, credentials, git, installer, hass, targets, hosts)
    updater = Updater(repos, credentials, vault, hass, settings)

    app[HOSTS] = hosts
    app[REPOS] = repos
    app[UPDATER] = updater

    background: list[asyncio.Task[None]] = []
    if settings.auto_lock_minutes > 0:
        background.append(asyncio.create_task(_auto_lock_loop(app)))
    if settings.update_interval_hours > 0:
        background.append(asyncio.create_task(updater.loop()))

    yield

    for task in background:
        task.cancel()
    for task in background:
        with contextlib.suppress(asyncio.CancelledError):
            await task
    await hass.close()
    await hosts.close()
    vault.shutdown()
    db.close()


def create_app(settings: Settings) -> web.Application:
    app = web.Application(middlewares=[peer_guard(settings), api.error_middleware])
    app[SETTINGS] = settings
    app.cleanup_ctx.append(_lifecycle)

    app.router.add_get("/", handle_index)
    app.router.add_get("/api/health", handle_health)
    app.router.add_get("/api/info", handle_info)
    api.register(app)

    assets = STATIC_DIR / "assets"
    if assets.is_dir():
        app.router.add_static("/assets/", assets, name="assets")

    return app
