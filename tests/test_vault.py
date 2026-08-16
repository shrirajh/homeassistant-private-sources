"""Vault envelope encryption, tier isolation, locking and backoff."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from psm import crypto
from psm.crypto import DecryptionError, ScryptParams, Sealed
from psm.db import Database
from psm.keystore import LocalKeystore
from psm.vault import (
    InvalidPassphrase,
    PassphraseAlreadySet,
    PassphraseNotSet,
    Tier,
    TooManyAttempts,
    Vault,
    VaultError,
    VaultLocked,
)

PASSPHRASE = "correct horse battery"
OTHER_PASSPHRASE = "incorrect zebra staple"

# Captured before the autouse fixture swaps in a cheap stub.
_REAL_CALIBRATE = crypto.calibrate


@pytest.fixture
def parts(tmp_path: Path) -> tuple[Database, LocalKeystore]:
    keystore_dir = tmp_path / "keystore"
    keystore_dir.mkdir()
    return Database(tmp_path / "psm.db"), LocalKeystore(keystore_dir)


@pytest.fixture
def vault(parts: tuple[Database, LocalKeystore]) -> Vault:
    instance = Vault(*parts)
    instance.start()
    return instance


def _add_credential(
    db: Database, vault: Vault, cred_id: str, kind: str, tier: Tier, secret: bytes
) -> None:
    sealed = vault.encrypt(tier, cred_id, kind, secret)
    db.execute(
        "INSERT INTO credentials (id, label, kind, tier, nonce, ciphertext) VALUES (?,?,?,?,?,?)",
        (cred_id, f"label-{cred_id}", kind, tier.value, sealed.nonce, sealed.ciphertext),
    )


def test_start_creates_key_file_and_tier(parts: tuple[Database, LocalKeystore]) -> None:
    db, keystore = parts
    assert not keystore.exists()

    vault = Vault(db, keystore)
    vault.start()

    assert keystore.exists()
    assert len(keystore.load()) == crypto.KEY_BYTES
    assert vault.available(Tier.UNATTENDED)
    assert not vault.passphrase_set


def test_unattended_secret_survives_restart(parts: tuple[Database, LocalKeystore]) -> None:
    db, keystore = parts
    first = Vault(db, keystore)
    first.start()
    sealed = first.encrypt(Tier.UNATTENDED, "cred-1", "token", b"ghp_secret")
    first.shutdown()

    second = Vault(db, keystore)
    second.start()
    assert second.decrypt(Tier.UNATTENDED, "cred-1", "token", sealed) == b"ghp_secret"


def test_losing_the_key_file_makes_the_tier_unrecoverable(
    parts: tuple[Database, LocalKeystore],
) -> None:
    db, keystore = parts
    first = Vault(db, keystore)
    first.start()
    keystore.destroy()

    with pytest.raises(DecryptionError):
        Vault(db, keystore).start()


async def test_protected_tier_round_trip(vault: Vault) -> None:
    await vault.set_passphrase(PASSPHRASE)
    assert vault.passphrase_set
    assert vault.unlocked

    sealed = vault.encrypt(Tier.PROTECTED, "cred-2", "ssh", b"PRIVATE KEY")
    assert vault.decrypt(Tier.PROTECTED, "cred-2", "ssh", sealed) == b"PRIVATE KEY"


async def test_lock_blocks_protected_but_not_unattended(vault: Vault) -> None:
    await vault.set_passphrase(PASSPHRASE)
    protected = vault.encrypt(Tier.PROTECTED, "cred-3", "token", b"protected")
    unattended = vault.encrypt(Tier.UNATTENDED, "cred-4", "token", b"unattended")

    vault.lock()
    assert not vault.unlocked

    with pytest.raises(VaultLocked):
        vault.decrypt(Tier.PROTECTED, "cred-3", "token", protected)
    assert vault.decrypt(Tier.UNATTENDED, "cred-4", "token", unattended) == b"unattended"

    await vault.unlock(PASSPHRASE)
    assert vault.decrypt(Tier.PROTECTED, "cred-3", "token", protected) == b"protected"


async def test_protected_tier_locked_after_restart(parts: tuple[Database, LocalKeystore]) -> None:
    db, keystore = parts
    first = Vault(db, keystore)
    first.start()
    await first.set_passphrase(PASSPHRASE)
    sealed = first.encrypt(Tier.PROTECTED, "cred-5", "token", b"secret")
    first.shutdown()

    second = Vault(db, keystore)
    second.start()
    assert second.passphrase_set
    assert not second.unlocked
    with pytest.raises(VaultLocked):
        second.decrypt(Tier.PROTECTED, "cred-5", "token", sealed)

    await second.unlock(PASSPHRASE)
    assert second.decrypt(Tier.PROTECTED, "cred-5", "token", sealed) == b"secret"


async def test_wrong_passphrase_is_rejected(vault: Vault) -> None:
    await vault.set_passphrase(PASSPHRASE)
    vault.lock()

    with pytest.raises(InvalidPassphrase):
        await vault.unlock(OTHER_PASSPHRASE)
    assert not vault.unlocked


async def test_lock_wipes_the_key_buffer(vault: Vault) -> None:
    await vault.set_passphrase(PASSPHRASE)
    buffer = vault._deks[Tier.PROTECTED]
    assert any(buffer)

    vault.lock()
    assert not any(buffer)


async def test_aad_binds_ciphertext_to_its_credential(vault: Vault) -> None:
    sealed = vault.encrypt(Tier.UNATTENDED, "cred-a", "token", b"secret")

    with pytest.raises(DecryptionError):
        vault.decrypt(Tier.UNATTENDED, "cred-b", "token", sealed)
    with pytest.raises(DecryptionError):
        vault.decrypt(Tier.UNATTENDED, "cred-a", "ssh", sealed)


async def test_tiers_cannot_decrypt_each_other(vault: Vault) -> None:
    await vault.set_passphrase(PASSPHRASE)
    sealed = vault.encrypt(Tier.PROTECTED, "cred-6", "token", b"secret")

    with pytest.raises(DecryptionError):
        vault.decrypt(Tier.UNATTENDED, "cred-6", "token", sealed)


async def test_wrap_aad_prevents_swapping_tier_rows(
    vault: Vault, parts: tuple[Database, LocalKeystore]
) -> None:
    db, keystore = parts
    await vault.set_passphrase(PASSPHRASE)

    protected = db.one("SELECT wrap_nonce, wrap_blob FROM vault WHERE tier = 'protected'")
    db.execute(
        "UPDATE vault SET wrap_nonce = ?, wrap_blob = ? WHERE tier = 'unattended'",
        (protected["wrap_nonce"], protected["wrap_blob"]),
    )

    with pytest.raises(DecryptionError):
        Vault(db, keystore).start()


async def test_change_passphrase_keeps_secrets_readable(vault: Vault) -> None:
    await vault.set_passphrase(PASSPHRASE)
    sealed = vault.encrypt(Tier.PROTECTED, "cred-7", "token", b"secret")

    await vault.change_passphrase(PASSPHRASE, OTHER_PASSPHRASE)
    vault.lock()

    with pytest.raises(InvalidPassphrase):
        await vault.unlock(PASSPHRASE)
    vault._reset_backoff()

    await vault.unlock(OTHER_PASSPHRASE)
    assert vault.decrypt(Tier.PROTECTED, "cred-7", "token", sealed) == b"secret"


async def test_change_passphrase_rejects_wrong_current(vault: Vault) -> None:
    await vault.set_passphrase(PASSPHRASE)
    with pytest.raises(InvalidPassphrase):
        await vault.change_passphrase(OTHER_PASSPHRASE, "brand new passphrase")


async def test_remove_passphrase_migrates_credentials_down(
    vault: Vault, parts: tuple[Database, LocalKeystore]
) -> None:
    db, _ = parts
    await vault.set_passphrase(PASSPHRASE)
    _add_credential(db, vault, "cred-8", "token", Tier.PROTECTED, b"secret")

    assert await vault.remove_passphrase(PASSPHRASE) == 1
    assert not vault.passphrase_set

    row = db.one("SELECT tier, nonce, ciphertext FROM credentials WHERE id = 'cred-8'")
    assert row["tier"] == Tier.UNATTENDED.value
    assert (
        vault.decrypt(Tier.UNATTENDED, "cred-8", "token", Sealed(row["nonce"], row["ciphertext"]))
        == b"secret"
    )


async def test_migrate_credential_between_tiers(
    vault: Vault, parts: tuple[Database, LocalKeystore]
) -> None:
    db, _ = parts
    await vault.set_passphrase(PASSPHRASE)
    _add_credential(db, vault, "cred-9", "ssh", Tier.UNATTENDED, b"key material")

    vault.migrate("cred-9", Tier.PROTECTED)

    row = db.one("SELECT tier, nonce, ciphertext FROM credentials WHERE id = 'cred-9'")
    assert row["tier"] == Tier.PROTECTED.value
    assert (
        vault.decrypt(Tier.PROTECTED, "cred-9", "ssh", Sealed(row["nonce"], row["ciphertext"]))
        == b"key material"
    )


async def test_migrate_unknown_credential(vault: Vault) -> None:
    with pytest.raises(VaultError):
        vault.migrate("missing", Tier.PROTECTED)


async def test_backoff_grows_and_blocks(vault: Vault) -> None:
    await vault.set_passphrase(PASSPHRASE)
    vault.lock()

    with pytest.raises(InvalidPassphrase):
        await vault.unlock(OTHER_PASSPHRASE)

    status = vault.status()
    assert status.failed_attempts == 1
    assert status.retry_after > 0

    with pytest.raises(TooManyAttempts):
        await vault.unlock(PASSPHRASE)


async def test_backoff_persists_across_restart(parts: tuple[Database, LocalKeystore]) -> None:
    db, keystore = parts
    first = Vault(db, keystore)
    first.start()
    await first.set_passphrase(PASSPHRASE)
    first.lock()
    with pytest.raises(InvalidPassphrase):
        await first.unlock(OTHER_PASSPHRASE)

    second = Vault(db, keystore)
    second.start()
    assert second.status().failed_attempts == 1
    with pytest.raises(TooManyAttempts):
        await second.unlock(PASSPHRASE)


async def test_successful_unlock_clears_backoff(vault: Vault) -> None:
    await vault.set_passphrase(PASSPHRASE)
    vault.lock()
    with pytest.raises(InvalidPassphrase):
        await vault.unlock(OTHER_PASSPHRASE)

    vault._reset_backoff()
    await vault.unlock(PASSPHRASE)
    assert vault.status().failed_attempts == 0
    assert vault.status().retry_after == 0


async def test_short_passphrase_rejected(vault: Vault) -> None:
    with pytest.raises(VaultError):
        await vault.set_passphrase("short")


async def test_set_passphrase_twice(vault: Vault) -> None:
    await vault.set_passphrase(PASSPHRASE)
    with pytest.raises(PassphraseAlreadySet):
        await vault.set_passphrase(OTHER_PASSPHRASE)


async def test_unlock_without_passphrase_configured(vault: Vault) -> None:
    with pytest.raises(PassphraseNotSet):
        await vault.unlock(PASSPHRASE)


async def test_auto_lock_respects_idle_window(vault: Vault) -> None:
    await vault.set_passphrase(PASSPHRASE)

    assert vault.maybe_auto_lock(0) is False
    assert vault.maybe_auto_lock(30) is False

    vault._last_use = time.monotonic() - 3600
    assert vault.maybe_auto_lock(30) is True
    assert not vault.unlocked


def test_calibrate_respects_bounds() -> None:
    assert _REAL_CALIBRATE(target_seconds=0.0).n == crypto.SCRYPT_MIN_N


def test_derive_works_at_maximum_cost() -> None:
    """Guards the maxmem calculation, which OpenSSL would otherwise reject."""
    params = ScryptParams(crypto.SCRYPT_MAX_N)
    key = crypto.derive_passphrase_key(PASSPHRASE, crypto.random_salt(), params)
    assert len(key) == crypto.KEY_BYTES
