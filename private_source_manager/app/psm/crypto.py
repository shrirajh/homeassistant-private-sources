"""Cryptographic primitives for the credential vault.

Envelope encryption throughout: a random data encryption key per tier protects the
secrets, and that DEK is itself wrapped either by a key file or by a passphrase.
"""

from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

KEY_BYTES = 32
NONCE_BYTES = 12
SALT_BYTES = 16

SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_MIN_N = 1 << 14
SCRYPT_MAX_N = 1 << 17
CALIBRATION_TARGET_SECONDS = 0.75

UNATTENDED_WRAP_INFO = b"psm-unattended-wrap-v1"


class DecryptionError(Exception):
    """Authenticated decryption failed: wrong key, wrong context, or tampering."""


@dataclass(frozen=True)
class Sealed:
    nonce: bytes
    ciphertext: bytes


@dataclass(frozen=True)
class ScryptParams:
    n: int
    r: int = SCRYPT_R
    p: int = SCRYPT_P


def random_key() -> bytes:
    return os.urandom(KEY_BYTES)


def random_salt() -> bytes:
    return os.urandom(SALT_BYTES)


def wrap_aad(tier: str) -> bytes:
    """Bind a wrapped DEK to its tier so the two wraps cannot be swapped."""
    return b"psm-dek-wrap-v1|" + tier.encode()


def secret_aad(credential_id: str, kind: str) -> bytes:
    """Bind a secret to its credential row so ciphertexts cannot be moved between rows."""
    return b"|".join((b"psm-secret-v1", credential_id.encode(), kind.encode()))


def seal(key: bytes, plaintext: bytes, aad: bytes) -> Sealed:
    nonce = os.urandom(NONCE_BYTES)
    return Sealed(nonce, AESGCM(key).encrypt(nonce, plaintext, aad))


def unseal(key: bytes, sealed: Sealed, aad: bytes) -> bytes:
    try:
        return AESGCM(key).decrypt(sealed.nonce, sealed.ciphertext, aad)
    except InvalidTag as err:
        raise DecryptionError("authentication failed") from err


def derive_wrap_key(secret: bytes, info: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=KEY_BYTES, salt=None, info=info).derive(secret)


def _maxmem(params: ScryptParams) -> int:
    # OpenSSL caps scrypt allocation at 32 MiB by default, well below what these
    # cost parameters need, so the limit has to be raised explicitly.
    return 256 * params.n * params.r + (1 << 20)


def derive_passphrase_key(passphrase: str, salt: bytes, params: ScryptParams) -> bytes:
    return hashlib.scrypt(
        passphrase.encode("utf-8"),
        salt=salt,
        n=params.n,
        r=params.r,
        p=params.p,
        dklen=KEY_BYTES,
        maxmem=_maxmem(params),
    )


def calibrate(target_seconds: float = CALIBRATION_TARGET_SECONDS) -> ScryptParams:
    """Pick the largest scrypt cost that stays near the target time on this hardware."""
    salt = random_salt()
    params = ScryptParams(SCRYPT_MIN_N)
    while True:
        start = time.perf_counter()
        derive_passphrase_key("calibration", salt, params)
        elapsed = time.perf_counter() - start
        if elapsed >= target_seconds or params.n >= SCRYPT_MAX_N:
            return params
        params = ScryptParams(params.n << 1)


def wipe(buffer: bytearray | None) -> None:
    """Best effort overwrite. Python cannot guarantee no copy survives elsewhere."""
    if buffer is None:
        return
    for index in range(len(buffer)):
        buffer[index] = 0
