"""Two tier credential vault.

Each tier owns a random data encryption key. The unattended DEK is wrapped by a key
file on disk, so background updates keep working after a reboot. The protected DEK is
wrapped by a passphrase that is never written anywhere, so it stays unavailable until
somebody unlocks the vault.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import StrEnum

from . import crypto
from .crypto import DecryptionError, ScryptParams, Sealed
from .db import Database
from .keystore import LocalKeystore

_LOGGER = logging.getLogger(__name__)

MAX_BACKOFF_SECONDS = 300.0
MIN_PASSPHRASE_LENGTH = 10


class Tier(StrEnum):
    UNATTENDED = "unattended"
    PROTECTED = "protected"


class VaultError(Exception):
    """Base class for vault failures."""


class VaultLocked(VaultError):
    """A protected tier secret was needed while the vault was locked."""


class InvalidPassphrase(VaultError):
    """The supplied passphrase did not unwrap the protected DEK."""


class PassphraseNotSet(VaultError):
    """No protected tier exists."""


class PassphraseAlreadySet(VaultError):
    """A protected tier already exists."""


class TooManyAttempts(VaultError):
    def __init__(self, retry_after: float) -> None:
        super().__init__(f"too many attempts, retry in {int(retry_after) + 1}s")
        self.retry_after = retry_after


@dataclass(frozen=True)
class VaultStatus:
    passphrase_set: bool
    unlocked: bool
    failed_attempts: int
    retry_after: float
    kdf_n: int | None


def _validate(passphrase: str) -> None:
    if len(passphrase) < MIN_PASSPHRASE_LENGTH:
        raise VaultError(f"passphrase must be at least {MIN_PASSPHRASE_LENGTH} characters")


class Vault:
    def __init__(self, db: Database, keystore: LocalKeystore) -> None:
        self._db = db
        self._keystore = keystore
        self._deks: dict[Tier, bytearray] = {}
        self._last_use = time.monotonic()

    def start(self) -> None:
        """Load the unattended DEK, creating the tier and its key file on first run."""
        wrap_key = crypto.derive_wrap_key(
            self._keystore.load_or_create(), crypto.UNATTENDED_WRAP_INFO
        )
        aad = crypto.wrap_aad(Tier.UNATTENDED.value)
        row = self._db.one("SELECT * FROM vault WHERE tier = ?", (Tier.UNATTENDED.value,))

        if row is None:
            dek = crypto.random_key()
            sealed = crypto.seal(wrap_key, dek, aad)
            self._db.execute(
                "INSERT INTO vault (tier, wrap_nonce, wrap_blob) VALUES (?, ?, ?)",
                (Tier.UNATTENDED.value, sealed.nonce, sealed.ciphertext),
            )
            _LOGGER.info("Created unattended vault tier")
        else:
            dek = crypto.unseal(wrap_key, Sealed(row["wrap_nonce"], row["wrap_blob"]), aad)

        self._deks[Tier.UNATTENDED] = bytearray(dek)

    def shutdown(self) -> None:
        for buffer in self._deks.values():
            crypto.wipe(buffer)
        self._deks.clear()

    @property
    def passphrase_set(self) -> bool:
        return (
            self._db.one("SELECT 1 FROM vault WHERE tier = ?", (Tier.PROTECTED.value,)) is not None
        )

    @property
    def unlocked(self) -> bool:
        return Tier.PROTECTED in self._deks

    def available(self, tier: Tier) -> bool:
        return tier in self._deks

    def status(self) -> VaultStatus:
        state = self._db.one("SELECT failed_attempts, locked_until FROM unlock_state WHERE id = 1")
        protected = self._db.one("SELECT kdf_n FROM vault WHERE tier = ?", (Tier.PROTECTED.value,))
        locked_until = (state["locked_until"] if state else None) or 0.0
        return VaultStatus(
            passphrase_set=protected is not None,
            unlocked=self.unlocked,
            failed_attempts=state["failed_attempts"] if state else 0,
            retry_after=max(0.0, locked_until - time.time()),
            kdf_n=protected["kdf_n"] if protected else None,
        )

    def encrypt(self, tier: Tier, credential_id: str, kind: str, secret: bytes) -> Sealed:
        return crypto.seal(self._dek(tier), secret, crypto.secret_aad(credential_id, kind))

    def decrypt(self, tier: Tier, credential_id: str, kind: str, sealed: Sealed) -> bytes:
        return crypto.unseal(self._dek(tier), sealed, crypto.secret_aad(credential_id, kind))

    async def set_passphrase(self, passphrase: str) -> ScryptParams:
        if self.passphrase_set:
            raise PassphraseAlreadySet("a passphrase is already configured")
        _validate(passphrase)

        params = await asyncio.to_thread(crypto.calibrate)
        salt = crypto.random_salt()
        kek = await asyncio.to_thread(crypto.derive_passphrase_key, passphrase, salt, params)

        dek = crypto.random_key()
        sealed = crypto.seal(kek, dek, crypto.wrap_aad(Tier.PROTECTED.value))
        self._db.execute(
            """INSERT INTO vault (tier, wrap_nonce, wrap_blob, kdf, kdf_salt, kdf_n, kdf_r, kdf_p)
               VALUES (?, ?, ?, 'scrypt', ?, ?, ?, ?)""",
            (
                Tier.PROTECTED.value,
                sealed.nonce,
                sealed.ciphertext,
                salt,
                params.n,
                params.r,
                params.p,
            ),
        )
        self._deks[Tier.PROTECTED] = bytearray(dek)
        self._last_use = time.monotonic()
        _LOGGER.info("Protected tier created with scrypt n=%d", params.n)
        return params

    async def unlock(self, passphrase: str) -> None:
        if self.unlocked:
            return
        dek = await self._unwrap_protected(passphrase)
        self._deks[Tier.PROTECTED] = bytearray(dek)
        self._last_use = time.monotonic()
        _LOGGER.info("Vault unlocked")

    def lock(self) -> None:
        buffer = self._deks.pop(Tier.PROTECTED, None)
        if buffer is not None:
            crypto.wipe(buffer)
            _LOGGER.info("Vault locked")

    async def change_passphrase(self, old: str, new: str) -> ScryptParams:
        _validate(new)
        dek = await self._unwrap_protected(old)

        params = await asyncio.to_thread(crypto.calibrate)
        salt = crypto.random_salt()
        kek = await asyncio.to_thread(crypto.derive_passphrase_key, new, salt, params)
        sealed = crypto.seal(kek, dek, crypto.wrap_aad(Tier.PROTECTED.value))

        self._db.execute(
            """UPDATE vault
                  SET wrap_nonce = ?, wrap_blob = ?, kdf_salt = ?, kdf_n = ?, kdf_r = ?, kdf_p = ?,
                      updated_at = datetime('now')
                WHERE tier = ?""",
            (
                sealed.nonce,
                sealed.ciphertext,
                salt,
                params.n,
                params.r,
                params.p,
                Tier.PROTECTED.value,
            ),
        )
        self._deks[Tier.PROTECTED] = bytearray(dek)
        _LOGGER.info("Passphrase changed, scrypt n=%d", params.n)
        return params

    async def remove_passphrase(self, passphrase: str) -> int:
        """Drop the protected tier, moving any credentials it held down to unattended."""
        dek = await self._unwrap_protected(passphrase)
        self._deks[Tier.PROTECTED] = bytearray(dek)

        moved = self.migrate_all(Tier.PROTECTED, Tier.UNATTENDED)
        crypto.wipe(self._deks.pop(Tier.PROTECTED, None))
        self._db.execute("DELETE FROM vault WHERE tier = ?", (Tier.PROTECTED.value,))
        _LOGGER.info("Protected tier removed, %d credentials moved to unattended", moved)
        return moved

    def migrate(self, credential_id: str, target: Tier) -> None:
        row = self._db.one(
            "SELECT id, kind, tier, nonce, ciphertext FROM credentials WHERE id = ?",
            (credential_id,),
        )
        if row is None:
            raise VaultError(f"unknown credential {credential_id}")

        source = Tier(row["tier"])
        if source is target:
            return

        secret = self.decrypt(
            source, row["id"], row["kind"], Sealed(row["nonce"], row["ciphertext"])
        )
        sealed = self.encrypt(target, row["id"], row["kind"], secret)
        self._db.execute(
            "UPDATE credentials SET tier = ?, nonce = ?, ciphertext = ? WHERE id = ?",
            (target.value, sealed.nonce, sealed.ciphertext, row["id"]),
        )

    def migrate_all(self, source: Tier, target: Tier) -> int:
        rows = self._db.all("SELECT id FROM credentials WHERE tier = ?", (source.value,))
        for row in rows:
            self.migrate(row["id"], target)
        return len(rows)

    def idle_seconds(self) -> float:
        return time.monotonic() - self._last_use

    def maybe_auto_lock(self, minutes: int) -> bool:
        if minutes <= 0 or not self.unlocked or self.idle_seconds() < minutes * 60:
            return False
        self.lock()
        _LOGGER.info("Vault auto locked after %d idle minutes", minutes)
        return True

    def _dek(self, tier: Tier) -> bytes:
        buffer = self._deks.get(tier)
        if buffer is None:
            if tier is Tier.PROTECTED:
                raise VaultLocked("vault is locked")
            raise VaultError("unattended tier is not ready")
        self._last_use = time.monotonic()
        return bytes(buffer)

    async def _unwrap_protected(self, passphrase: str) -> bytes:
        row = self._db.one("SELECT * FROM vault WHERE tier = ?", (Tier.PROTECTED.value,))
        if row is None:
            raise PassphraseNotSet("no passphrase is configured")

        self._enforce_backoff()
        params = ScryptParams(row["kdf_n"], row["kdf_r"], row["kdf_p"])
        kek = await asyncio.to_thread(
            crypto.derive_passphrase_key, passphrase, row["kdf_salt"], params
        )
        try:
            dek = crypto.unseal(
                kek,
                Sealed(row["wrap_nonce"], row["wrap_blob"]),
                crypto.wrap_aad(Tier.PROTECTED.value),
            )
        except DecryptionError as err:
            self._record_failure()
            raise InvalidPassphrase("passphrase rejected") from err

        self._reset_backoff()
        return dek

    def _enforce_backoff(self) -> None:
        row = self._db.one("SELECT locked_until FROM unlock_state WHERE id = 1")
        remaining = ((row["locked_until"] if row else None) or 0.0) - time.time()
        if remaining > 0:
            raise TooManyAttempts(remaining)

    def _record_failure(self) -> None:
        row = self._db.one("SELECT failed_attempts FROM unlock_state WHERE id = 1")
        attempts = (row["failed_attempts"] if row else 0) + 1
        delay = min(2.0 ** (attempts - 1), MAX_BACKOFF_SECONDS)
        self._db.execute(
            "UPDATE unlock_state SET failed_attempts = ?, locked_until = ? WHERE id = 1",
            (attempts, time.time() + delay),
        )
        _LOGGER.warning("Rejected unlock attempt %d, backing off %.0fs", attempts, delay)

    def _reset_backoff(self) -> None:
        self._db.execute(
            "UPDATE unlock_state SET failed_attempts = 0, locked_until = NULL WHERE id = 1"
        )
