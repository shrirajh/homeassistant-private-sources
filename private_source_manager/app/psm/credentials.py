"""Per repository credential storage.

Secrets go through the vault; public keys and fingerprints stay in plaintext so a
deploy key can still be copied out of the UI while the vault is locked.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from uuid import uuid4

from . import sshkeys
from .crypto import Sealed
from .db import Database
from .vault import Tier, Vault, VaultError

_LOGGER = logging.getLogger(__name__)


class CredentialKind(StrEnum):
    SSH = "ssh"
    TOKEN = "token"  # noqa: S105


class UnknownCredential(VaultError):
    """No credential with that identifier."""


class CredentialInUse(VaultError):
    """The credential is still attached to one or more repositories."""


@dataclass(frozen=True)
class Credential:
    id: str
    label: str
    kind: CredentialKind
    tier: Tier
    username: str | None
    public_key: str | None
    fingerprint: str | None
    created_at: str
    repo_count: int

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "label": self.label,
            "kind": self.kind.value,
            "tier": self.tier.value,
            "username": self.username,
            "public_key": self.public_key,
            "fingerprint": self.fingerprint,
            "created_at": self.created_at,
            "repo_count": self.repo_count,
        }


_SELECT = """
SELECT c.id, c.label, c.kind, c.tier, c.username, c.public_key, c.fingerprint, c.created_at,
       (SELECT COUNT(*) FROM repos r WHERE r.credential_id = c.id) AS repo_count
  FROM credentials c
"""


def _row_to_credential(row) -> Credential:
    return Credential(
        id=row["id"],
        label=row["label"],
        kind=CredentialKind(row["kind"]),
        tier=Tier(row["tier"]),
        username=row["username"],
        public_key=row["public_key"],
        fingerprint=row["fingerprint"],
        created_at=row["created_at"],
        repo_count=row["repo_count"],
    )


class CredentialStore:
    def __init__(self, db: Database, vault: Vault) -> None:
        self._db = db
        self._vault = vault

    def list(self) -> list[Credential]:
        return [
            _row_to_credential(row) for row in self._db.all(f"{_SELECT} ORDER BY c.created_at DESC")
        ]

    def get(self, credential_id: str) -> Credential:
        row = self._db.one(f"{_SELECT} WHERE c.id = ?", (credential_id,))
        if row is None:
            raise UnknownCredential(f"no credential {credential_id}")
        return _row_to_credential(row)

    def create_ssh(self, label: str, tier: Tier, material: bytes | None = None) -> Credential:
        pair = (
            sshkeys.import_private(material, comment=label)
            if material
            else sshkeys.generate(comment=label)
        )
        return self._insert(
            label=label,
            kind=CredentialKind.SSH,
            tier=tier,
            secret=pair.private_key,
            public_key=pair.public_key,
            fingerprint=pair.fingerprint,
        )

    def create_token(
        self, label: str, tier: Tier, token: str, username: str | None = None
    ) -> Credential:
        return self._insert(
            label=label,
            kind=CredentialKind.TOKEN,
            tier=tier,
            secret=token.encode("utf-8"),
            username=username,
        )

    def rotate_ssh(self, credential_id: str) -> Credential:
        existing = self.get(credential_id)
        if existing.kind is not CredentialKind.SSH:
            raise VaultError("only ssh credentials can be rotated")

        pair = sshkeys.generate(comment=existing.label)
        sealed = self._vault.encrypt(
            existing.tier, credential_id, CredentialKind.SSH.value, pair.private_key
        )
        self._db.execute(
            "UPDATE credentials SET nonce = ?, ciphertext = ?, public_key = ?, fingerprint = ? "
            "WHERE id = ?",
            (sealed.nonce, sealed.ciphertext, pair.public_key, pair.fingerprint, credential_id),
        )
        _LOGGER.info("Rotated ssh credential %s", credential_id)
        return self.get(credential_id)

    def set_tier(self, credential_id: str, tier: Tier) -> Credential:
        self.get(credential_id)
        self._require_tier(tier)
        self._vault.migrate(credential_id, tier)
        return self.get(credential_id)

    def delete(self, credential_id: str) -> None:
        credential = self.get(credential_id)
        if credential.repo_count:
            raise CredentialInUse(
                f"still used by {credential.repo_count} repositor"
                f"{'y' if credential.repo_count == 1 else 'ies'}"
            )
        self._db.execute("DELETE FROM credentials WHERE id = ?", (credential_id,))
        _LOGGER.info("Deleted credential %s", credential_id)

    def secret(self, credential_id: str) -> bytes:
        """Decrypt for internal use by the git layer. Never returned over HTTP."""
        row = self._db.one(
            "SELECT id, kind, tier, nonce, ciphertext FROM credentials WHERE id = ?",
            (credential_id,),
        )
        if row is None:
            raise UnknownCredential(f"no credential {credential_id}")
        return self._vault.decrypt(
            Tier(row["tier"]), row["id"], row["kind"], Sealed(row["nonce"], row["ciphertext"])
        )

    def _require_tier(self, tier: Tier) -> None:
        if tier is Tier.PROTECTED and not self._vault.passphrase_set:
            raise VaultError("set a passphrase before using the protected tier")

    def _insert(
        self,
        *,
        label: str,
        kind: CredentialKind,
        tier: Tier,
        secret: bytes,
        public_key: str | None = None,
        fingerprint: str | None = None,
        username: str | None = None,
    ) -> Credential:
        self._require_tier(tier)
        credential_id = uuid4().hex
        sealed = self._vault.encrypt(tier, credential_id, kind.value, secret)
        self._db.execute(
            """INSERT INTO credentials
                   (id, label, kind, tier, username, public_key, fingerprint, nonce, ciphertext)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                credential_id,
                label,
                kind.value,
                tier.value,
                username,
                public_key,
                fingerprint,
                sealed.nonce,
                sealed.ciphertext,
            ),
        )
        _LOGGER.info("Created %s credential %s in the %s tier", kind.value, credential_id, tier)
        return self.get(credential_id)
