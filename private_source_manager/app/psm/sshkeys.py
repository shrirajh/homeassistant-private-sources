"""Ed25519 deploy key generation and import."""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

_ENCRYPTED = "passphrase protected keys are not supported, decrypt it first"


class InvalidKeyMaterial(ValueError):
    """Raised when key material cannot be parsed or is unusable."""


@dataclass(frozen=True)
class KeyPair:
    private_key: bytes
    public_key: str
    fingerprint: str


def fingerprint(public_key: str) -> str:
    """SHA256 fingerprint in the format ssh-keygen -lf prints."""
    parts = public_key.split()
    if len(parts) < 2:
        raise InvalidKeyMaterial("not an OpenSSH public key")
    try:
        blob = base64.b64decode(parts[1], validate=True)
    except ValueError as err:
        raise InvalidKeyMaterial("public key body is not valid base64") from err
    digest = hashlib.sha256(blob).digest()
    return "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("=")


def _pair(key: Ed25519PrivateKey, comment: str) -> KeyPair:
    private = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH,
        )
        .decode("ascii")
    )
    if comment:
        public = f"{public} {comment}"
    return KeyPair(private, public, fingerprint(public))


def generate(comment: str = "") -> KeyPair:
    return _pair(Ed25519PrivateKey.generate(), comment)


def import_private(material: bytes, comment: str = "") -> KeyPair:
    """Accept a pasted private key, normalising it to unencrypted OpenSSH format."""
    key = _load(material)
    public = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH,
        )
        .decode("ascii")
    )
    if comment:
        public = f"{public} {comment}"
    private = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return KeyPair(private, public, fingerprint(public))


def _load(material: bytes):
    # git runs with BatchMode, so an encrypted key could never be used unattended.
    # TypeError means a password was required; UnsupportedAlgorithm is how an encrypted
    # OpenSSH key surfaces when bcrypt is absent, which it is in the add-on image.
    for loader in (serialization.load_ssh_private_key, serialization.load_pem_private_key):
        try:
            return loader(material, password=None)
        except (TypeError, UnsupportedAlgorithm) as err:
            raise InvalidKeyMaterial(_ENCRYPTED) from err
        except ValueError:
            continue
    raise InvalidKeyMaterial("could not parse this private key")
