"""Vault HTTP API."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer

from psm.server import create_app

from conftest import make_settings

PASSPHRASE = "correct horse battery"
OTHER = "incorrect zebra staple"


@pytest.fixture
async def client(tmp_path: Path) -> AsyncIterator[TestClient]:
    app = create_app(make_settings(tmp_path))
    async with TestClient(TestServer(app)) as instance:
        yield instance


async def test_initial_status(client: TestClient) -> None:
    res = await client.get("/api/vault")
    assert res.status == 200
    payload = await res.json()
    assert payload["passphrase_set"] is False
    assert payload["unlocked"] is False
    assert payload["failed_attempts"] == 0


async def test_set_passphrase_then_lock_and_unlock(client: TestClient) -> None:
    res = await client.post("/api/vault/passphrase", json={"passphrase": PASSPHRASE})
    assert res.status == 200
    payload = await res.json()
    assert payload["passphrase_set"] is True
    assert payload["unlocked"] is True
    assert payload["kdf_n"] > 0

    assert (await (await client.post("/api/vault/lock")).json())["unlocked"] is False

    res = await client.post("/api/vault/unlock", json={"passphrase": PASSPHRASE})
    assert res.status == 200
    assert (await res.json())["unlocked"] is True


async def test_wrong_passphrase_is_unauthorised(client: TestClient) -> None:
    await client.post("/api/vault/passphrase", json={"passphrase": PASSPHRASE})
    await client.post("/api/vault/lock")

    res = await client.post("/api/vault/unlock", json={"passphrase": OTHER})
    assert res.status == 401
    assert (await res.json())["code"] == "InvalidPassphrase"


async def test_backoff_returns_retry_after(client: TestClient) -> None:
    await client.post("/api/vault/passphrase", json={"passphrase": PASSPHRASE})
    await client.post("/api/vault/lock")
    await client.post("/api/vault/unlock", json={"passphrase": OTHER})

    res = await client.post("/api/vault/unlock", json={"passphrase": PASSPHRASE})
    assert res.status == 429
    assert int(res.headers["Retry-After"]) >= 1
    assert (await res.json())["code"] == "TooManyAttempts"


async def test_setting_passphrase_twice_conflicts(client: TestClient) -> None:
    await client.post("/api/vault/passphrase", json={"passphrase": PASSPHRASE})
    res = await client.post("/api/vault/passphrase", json={"passphrase": OTHER})
    assert res.status == 409
    assert (await res.json())["code"] == "PassphraseAlreadySet"


async def test_unlock_without_passphrase_conflicts(client: TestClient) -> None:
    res = await client.post("/api/vault/unlock", json={"passphrase": PASSPHRASE})
    assert res.status == 409
    assert (await res.json())["code"] == "PassphraseNotSet"


async def test_change_passphrase(client: TestClient) -> None:
    await client.post("/api/vault/passphrase", json={"passphrase": PASSPHRASE})

    res = await client.put("/api/vault/passphrase", json={"current": PASSPHRASE, "new": OTHER})
    assert res.status == 200

    await client.post("/api/vault/lock")
    assert (await client.post("/api/vault/unlock", json={"passphrase": OTHER})).status == 200


async def test_remove_passphrase(client: TestClient) -> None:
    await client.post("/api/vault/passphrase", json={"passphrase": PASSPHRASE})

    res = await client.delete("/api/vault/passphrase", json={"passphrase": PASSPHRASE})
    assert res.status == 200
    payload = await res.json()
    assert payload["passphrase_set"] is False
    assert payload["migrated"] == 0


async def test_short_passphrase_is_rejected(client: TestClient) -> None:
    res = await client.post("/api/vault/passphrase", json={"passphrase": "short"})
    assert res.status == 400


async def test_missing_field(client: TestClient) -> None:
    res = await client.post("/api/vault/passphrase", json={})
    assert res.status == 400
    assert "passphrase" in (await res.json())["error"]


async def test_malformed_body(client: TestClient) -> None:
    res = await client.post(
        "/api/vault/passphrase", data="not json", headers={"Content-Type": "application/json"}
    )
    assert res.status == 400
