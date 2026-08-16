"""Ingress peer restriction and base href rewriting."""

from __future__ import annotations

from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer, make_mocked_request

from psm import ingress
from psm.config import Settings
from psm.server import create_app


def _settings(tmp_path: Path, *, dev_mode: bool) -> Settings:
    return Settings(
        dev_mode=dev_mode,
        log_level="info",
        host="127.0.0.1",
        port=0,
        data_dir=tmp_path / "data",
        ha_config_dir=tmp_path / "homeassistant",
        addons_dir=tmp_path / "addons",
        update_interval_hours=6,
        auto_lock_minutes=0,
        notify_on_update=True,
        supervisor_token=None,
    )


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (None, "/"),
        ("", "/"),
        ("   ", "/"),
        ("/api/hassio_ingress/tok", "/api/hassio_ingress/tok/"),
        ("/api/hassio_ingress/tok/", "/api/hassio_ingress/tok/"),
    ],
)
def test_base_href(header: str | None, expected: str) -> None:
    headers = {} if header is None else {ingress.INGRESS_PATH_HEADER: header}
    request = make_mocked_request("GET", "/", headers=headers)
    assert ingress.base_href(request) == expected


async def test_peer_guard_rejects_foreign_peer(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path, dev_mode=False))
    async with TestClient(TestServer(app)) as client:
        assert (await client.get("/api/health")).status == 403


async def test_peer_guard_allows_supervisor(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(ingress, "SUPERVISOR_PEER", "127.0.0.1")
    app = create_app(_settings(tmp_path, dev_mode=False))
    async with TestClient(TestServer(app)) as client:
        assert (await client.get("/api/health")).status == 200


async def test_dev_mode_skips_peer_guard(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path, dev_mode=True))
    async with TestClient(TestServer(app)) as client:
        assert (await client.get("/api/health")).status == 200


async def test_index_rewrites_base_href(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path, dev_mode=True))
    async with TestClient(TestServer(app)) as client:
        res = await client.get(
            "/", headers={ingress.INGRESS_PATH_HEADER: "/api/hassio_ingress/xyz"}
        )
        assert res.headers["Cache-Control"] == "no-store"
        body = await res.text()
        assert '<base href="/api/hassio_ingress/xyz/">' in body
        assert '<base href="/">' not in body
