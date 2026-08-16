"""Ingress plumbing: peer restriction and base href resolution."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from aiohttp import web

from .config import SUPERVISOR_PEER, Settings

_LOGGER = logging.getLogger(__name__)

INGRESS_PATH_HEADER = "X-Ingress-Path"

Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]


def peer_guard(settings: Settings):
    """Reject anything that did not arrive through the Supervisor ingress proxy."""

    @web.middleware
    async def middleware(request: web.Request, handler: Handler) -> web.StreamResponse:
        if settings.dev_mode:
            return await handler(request)
        if request.remote != SUPERVISOR_PEER:
            _LOGGER.warning("Rejected %s %s from %s", request.method, request.path, request.remote)
            raise web.HTTPForbidden(text="Reachable through Home Assistant ingress only")
        return await handler(request)

    return middleware


def base_href(request: web.Request) -> str:
    """Return the prefix the browser sees, so relative URLs resolve inside the iframe."""
    raw = request.headers.get(INGRESS_PATH_HEADER, "").strip()
    if not raw:
        return "/"
    return raw.rstrip("/") + "/"
