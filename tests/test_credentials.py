"""SSH key handling and the credential store."""

from __future__ import annotations

from pathlib import Path

import pytest
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from psm import sshkeys
from psm.credentials import (
    CredentialInUse,
    CredentialKind,
    CredentialStore,
    UnknownCredential,
)
from psm.db import Database
from psm.keystore import LocalKeystore
from psm.sshkeys import InvalidKeyMaterial
from psm.vault import Tier, Vault, VaultError, VaultLocked

PASSPHRASE = "correct horse battery"
TOKEN = "ghp_ThisIsAVerySecretTokenValue1234567890"  # noqa: S105


@pytest.fixture
def store(tmp_path: Path) -> CredentialStore:
    keystore_dir = tmp_path / "keystore"
    keystore_dir.mkdir()
    db = Database(tmp_path / "psm.db")
    vault = Vault(db, LocalKeystore(keystore_dir))
    vault.start()
    return CredentialStore(db, vault)


def test_generate_produces_an_openssh_ed25519_key() -> None:
    pair = sshkeys.generate(comment="my-repo")

    assert pair.public_key.startswith("ssh-ed25519 ")
    assert pair.public_key.endswith(" my-repo")
    assert pair.fingerprint.startswith("SHA256:")
    assert b"BEGIN OPENSSH PRIVATE KEY" in pair.private_key
    serialization.load_ssh_private_key(pair.private_key, password=None)


def test_import_round_trips_a_generated_key() -> None:
    original = sshkeys.generate(comment="label")
    imported = sshkeys.import_private(original.private_key, comment="label")

    assert imported.public_key == original.public_key
    assert imported.fingerprint == original.fingerprint


def test_import_rejects_garbage() -> None:
    with pytest.raises(InvalidKeyMaterial):
        sshkeys.import_private(b"definitely not a key")


def test_import_rejects_encrypted_keys() -> None:
    encrypted = Ed25519PrivateKey.generate().private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(b"hunter2hunter2"),
    )
    with pytest.raises(InvalidKeyMaterial, match="passphrase protected"):
        sshkeys.import_private(encrypted)


def test_import_reports_encrypted_openssh_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without bcrypt, an encrypted OpenSSH key raises UnsupportedAlgorithm, not TypeError."""

    def _unsupported(*args: object, **kwargs: object) -> None:
        raise UnsupportedAlgorithm("Need bcrypt module")

    monkeypatch.setattr(serialization, "load_ssh_private_key", _unsupported)
    with pytest.raises(InvalidKeyMaterial, match="passphrase protected"):
        sshkeys.import_private(b"-----BEGIN OPENSSH PRIVATE KEY-----")


def test_fingerprint_rejects_malformed_input() -> None:
    with pytest.raises(InvalidKeyMaterial):
        sshkeys.fingerprint("ssh-ed25519")


def test_create_ssh_keeps_public_key_readable(store: CredentialStore) -> None:
    credential = store.create_ssh("deploy key", Tier.UNATTENDED)

    assert credential.kind is CredentialKind.SSH
    assert credential.public_key.startswith("ssh-ed25519 ")
    assert credential.fingerprint.startswith("SHA256:")
    assert credential.repo_count == 0

    secret = store.secret(credential.id)
    assert b"BEGIN OPENSSH PRIVATE KEY" in secret


def test_create_token_round_trip(store: CredentialStore) -> None:
    credential = store.create_token("gh token", Tier.UNATTENDED, TOKEN, username="x-access-token")

    assert credential.kind is CredentialKind.TOKEN
    assert credential.username == "x-access-token"
    assert credential.public_key is None
    assert store.secret(credential.id).decode() == TOKEN


def test_secrets_are_not_greppable_on_disk(store: CredentialStore, tmp_path: Path) -> None:
    """The headline requirement: no plaintext secret anywhere under the data directory."""
    store.create_token("gh token", Tier.UNATTENDED, TOKEN)
    pair_public = store.create_ssh("deploy key", Tier.UNATTENDED).public_key

    haystack = b""
    for path in tmp_path.rglob("*"):
        if path.is_file():
            haystack += path.read_bytes()

    assert TOKEN.encode() not in haystack
    assert b"BEGIN OPENSSH PRIVATE KEY" not in haystack
    # Public material is deliberately stored in the clear.
    assert pair_public.split()[1].encode() in haystack


def test_protected_tier_requires_a_passphrase(store: CredentialStore) -> None:
    with pytest.raises(VaultError, match="set a passphrase"):
        store.create_ssh("deploy key", Tier.PROTECTED)


async def test_protected_credential_is_unreadable_when_locked(store: CredentialStore) -> None:
    await store._vault.set_passphrase(PASSPHRASE)
    credential = store.create_token("token", Tier.PROTECTED, TOKEN)

    store._vault.lock()
    with pytest.raises(VaultLocked):
        store.secret(credential.id)

    await store._vault.unlock(PASSPHRASE)
    assert store.secret(credential.id).decode() == TOKEN


def test_rotate_replaces_the_key_but_keeps_the_row(store: CredentialStore) -> None:
    credential = store.create_ssh("deploy key", Tier.UNATTENDED)
    before = store.secret(credential.id)

    rotated = store.rotate_ssh(credential.id)

    assert rotated.id == credential.id
    assert rotated.public_key != credential.public_key
    assert rotated.fingerprint != credential.fingerprint
    assert store.secret(credential.id) != before


def test_rotate_rejects_token_credentials(store: CredentialStore) -> None:
    credential = store.create_token("token", Tier.UNATTENDED, TOKEN)
    with pytest.raises(VaultError, match="only ssh"):
        store.rotate_ssh(credential.id)


async def test_set_tier_migrates_the_secret(store: CredentialStore) -> None:
    await store._vault.set_passphrase(PASSPHRASE)
    credential = store.create_token("token", Tier.UNATTENDED, TOKEN)

    moved = store.set_tier(credential.id, Tier.PROTECTED)
    assert moved.tier is Tier.PROTECTED
    assert store.secret(credential.id).decode() == TOKEN

    store._vault.lock()
    with pytest.raises(VaultLocked):
        store.secret(credential.id)


def test_delete_blocked_while_a_repo_uses_it(store: CredentialStore) -> None:
    credential = store.create_ssh("deploy key", Tier.UNATTENDED)
    store._db.execute(
        """INSERT INTO repos (id, url, host, owner, name, category, credential_id)
           VALUES ('r1', 'git@github.com:a/b.git', 'github.com', 'a', 'b', 'integration', ?)""",
        (credential.id,),
    )

    assert store.get(credential.id).repo_count == 1
    with pytest.raises(CredentialInUse):
        store.delete(credential.id)

    store._db.execute("DELETE FROM repos WHERE id = 'r1'")
    store.delete(credential.id)
    with pytest.raises(UnknownCredential):
        store.get(credential.id)


def test_unknown_credential(store: CredentialStore) -> None:
    with pytest.raises(UnknownCredential):
        store.get("nope")
    with pytest.raises(UnknownCredential):
        store.secret("nope")


def test_list_orders_and_counts(store: CredentialStore) -> None:
    store.create_ssh("first", Tier.UNATTENDED)
    store.create_token("second", Tier.UNATTENDED, TOKEN)

    labels = {c.label for c in store.list()}
    assert labels == {"first", "second"}
    assert all(c.repo_count == 0 for c in store.list())
