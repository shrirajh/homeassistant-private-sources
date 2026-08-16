"""Credential HTTP API."""

from __future__ import annotations

from aiohttp.test_utils import TestClient

from psm import sshkeys

PASSPHRASE = "correct horse battery"
TOKEN = "ghp_ThisIsAVerySecretTokenValue1234567890"  # noqa: S105


async def _create_ssh(client: TestClient, label: str = "deploy key", tier: str = "unattended"):
    res = await client.post("/api/credentials", json={"kind": "ssh", "label": label, "tier": tier})
    return res, await res.json()


async def test_create_ssh_returns_public_material_only(client: TestClient) -> None:
    res, payload = await _create_ssh(client)

    assert res.status == 201
    assert payload["kind"] == "ssh"
    assert payload["tier"] == "unattended"
    assert payload["public_key"].startswith("ssh-ed25519 ")
    assert payload["fingerprint"].startswith("SHA256:")
    assert "private_key" not in payload
    assert "secret" not in payload


async def test_create_token(client: TestClient) -> None:
    res = await client.post(
        "/api/credentials",
        json={"kind": "token", "label": "gh", "token": TOKEN, "username": "x-access-token"},
    )
    payload = await res.json()

    assert res.status == 201
    assert payload["username"] == "x-access-token"
    assert payload["public_key"] is None
    assert TOKEN not in str(payload)


async def test_import_existing_key(client: TestClient) -> None:
    pair = sshkeys.generate(comment="imported")
    res = await client.post(
        "/api/credentials",
        json={
            "kind": "ssh",
            "label": "imported",
            "private_key": pair.private_key.decode(),
        },
    )
    payload = await res.json()

    assert res.status == 201
    assert payload["fingerprint"] == pair.fingerprint


async def test_import_invalid_key(client: TestClient) -> None:
    res = await client.post(
        "/api/credentials",
        json={"kind": "ssh", "label": "bad", "private_key": "not a key"},
    )
    assert res.status == 400
    assert (await res.json())["code"] == "InvalidKeyMaterial"


async def test_unknown_kind(client: TestClient) -> None:
    res = await client.post("/api/credentials", json={"kind": "magic", "label": "x"})
    assert res.status == 400


async def test_list_and_fetch(client: TestClient) -> None:
    _, created = await _create_ssh(client)

    listing = await (await client.get("/api/credentials")).json()
    assert [c["id"] for c in listing] == [created["id"]]

    fetched = await (await client.get(f"/api/credentials/{created['id']}")).json()
    assert fetched["id"] == created["id"]


async def test_unknown_credential_is_404(client: TestClient) -> None:
    assert (await client.get("/api/credentials/missing")).status == 404


async def test_rotate(client: TestClient) -> None:
    _, created = await _create_ssh(client)

    rotated = await (await client.post(f"/api/credentials/{created['id']}/rotate")).json()
    assert rotated["id"] == created["id"]
    assert rotated["fingerprint"] != created["fingerprint"]


async def test_rotate_token_is_rejected(client: TestClient) -> None:
    created = await (
        await client.post("/api/credentials", json={"kind": "token", "label": "t", "token": TOKEN})
    ).json()

    res = await client.post(f"/api/credentials/{created['id']}/rotate")
    assert res.status == 400


async def test_delete(client: TestClient) -> None:
    _, created = await _create_ssh(client)

    assert (await client.delete(f"/api/credentials/{created['id']}")).status == 200
    assert (await client.get(f"/api/credentials/{created['id']}")).status == 404


async def test_protected_tier_requires_passphrase(client: TestClient) -> None:
    res, _ = await _create_ssh(client, tier="protected")
    assert res.status == 400

    await client.post("/api/vault/passphrase", json={"passphrase": PASSPHRASE})
    res, payload = await _create_ssh(client, label="protected key", tier="protected")
    assert res.status == 201
    assert payload["tier"] == "protected"


async def test_creating_protected_credential_while_locked_is_423(client: TestClient) -> None:
    await client.post("/api/vault/passphrase", json={"passphrase": PASSPHRASE})
    await client.post("/api/vault/lock")

    res, _ = await _create_ssh(client, tier="protected")
    assert res.status == 423


async def test_change_tier(client: TestClient) -> None:
    await client.post("/api/vault/passphrase", json={"passphrase": PASSPHRASE})
    _, created = await _create_ssh(client)

    res = await client.put(f"/api/credentials/{created['id']}/tier", json={"tier": "protected"})
    assert res.status == 200
    assert (await res.json())["tier"] == "protected"


async def test_invalid_tier(client: TestClient) -> None:
    res, _ = await _create_ssh(client, tier="nonsense")
    assert res.status == 400
