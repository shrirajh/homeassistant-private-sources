"""aiohttp application wiring."""

from __future__ import annotations

import logging
from pathlib import Path

from aiohttp import web

from . import __version__
from .config import Settings
from .ingress import base_href, peer_guard

_LOGGER = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"

# Rewritten per request because the ingress prefix changes with the session token.
BASE_TAG = '<base href="/">'

SETTINGS: web.AppKey[Settings] = web.AppKey("settings", Settings)


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


def create_app(settings: Settings) -> web.Application:
    app = web.Application(middlewares=[peer_guard(settings)])
    app[SETTINGS] = settings

    app.router.add_get("/", handle_index)
    app.router.add_get("/api/health", handle_health)
    app.router.add_get("/api/info", handle_info)

    assets = STATIC_DIR / "assets"
    if assets.is_dir():
        app.router.add_static("/assets/", assets, name="assets")

    return app
