"""Add-on entry point."""

from __future__ import annotations

import logging
import sys

from aiohttp import web

from . import __version__, config
from .server import create_app

_LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"

_LEVELS = {
    "trace": logging.DEBUG,
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}


def main() -> int:
    settings = config.load()

    logging.basicConfig(
        level=_LEVELS.get(settings.log_level, logging.INFO),
        format=_LOG_FORMAT,
        stream=sys.stdout,
    )
    log = logging.getLogger("psm")

    settings.ensure_dirs()

    log.info(
        "Private Source Manager %s listening on %s:%s", __version__, settings.host, settings.port
    )
    if settings.dev_mode:
        log.warning("Development mode: ingress peer check is disabled")

    web.run_app(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        access_log=None,
        print=None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
