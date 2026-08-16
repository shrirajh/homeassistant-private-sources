"""Shared fixtures."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer

from psm import crypto
from psm.config import Settings
from psm.crypto import ScryptParams
from psm.server import create_app


@pytest.fixture(autouse=True)
def cheap_kdf(monkeypatch: pytest.MonkeyPatch) -> None:
    """Real calibration burns about a second of wall clock per call."""
    monkeypatch.setattr(crypto, "calibrate", lambda *args, **kwargs: ScryptParams(1 << 10))


@pytest.fixture
async def client(tmp_path: Path) -> AsyncIterator[TestClient]:
    app = create_app(make_settings(tmp_path))
    async with TestClient(TestServer(app)) as instance:
        yield instance


def make_settings(tmp_path: Path, *, dev_mode: bool = True, auto_lock_minutes: int = 0) -> Settings:
    return Settings(
        dev_mode=dev_mode,
        log_level="info",
        host="127.0.0.1",
        port=0,
        data_dir=tmp_path / "data",
        ha_config_dir=tmp_path / "homeassistant",
        addons_dir=tmp_path / "addons",
        update_interval_hours=6,
        auto_lock_minutes=auto_lock_minutes,
        notify_on_update=True,
        supervisor_token=None,
    )
