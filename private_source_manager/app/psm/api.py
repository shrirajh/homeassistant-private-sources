"""JSON API handlers."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiohttp import web

from .context import CREDENTIALS, SETTINGS, VAULT
from .credentials import CredentialInUse, CredentialKind, UnknownCredential
from .sshkeys import InvalidKeyMaterial
from .vault import (
    InvalidPassphrase,
    PassphraseAlreadySet,
    PassphraseNotSet,
    Tier,
    TooManyAttempts,
    VaultError,
    VaultLocked,
)

_LOGGER = logging.getLogger(__name__)

Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]

_STATUS_BY_ERROR: tuple[tuple[type[VaultError], int], ...] = (
    (VaultLocked, 423),
    (InvalidPassphrase, 401),
    (TooManyAttempts, 429),
    (PassphraseNotSet, 409),
    (PassphraseAlreadySet, 409),
    (UnknownCredential, 404),
    (CredentialInUse, 409),
)


class ApiError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


@web.middleware
async def error_middleware(request: web.Request, handler: Handler) -> web.StreamResponse:
    try:
        return await handler(request)
    except ApiError as err:
        return web.json_response({"error": err.message, "code": "ApiError"}, status=err.status)
    except InvalidKeyMaterial as err:
        return web.json_response({"error": str(err), "code": "InvalidKeyMaterial"}, status=400)
    except VaultError as err:
        status = next((s for kind, s in _STATUS_BY_ERROR if isinstance(err, kind)), 400)
        headers = {}
        if isinstance(err, TooManyAttempts):
            headers["Retry-After"] = str(int(err.retry_after) + 1)
        return web.json_response(
            {"error": str(err), "code": type(err).__name__}, status=status, headers=headers
        )


async def body(request: web.Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except ValueError as err:
        raise ApiError(400, "expected a JSON body") from err
    if not isinstance(payload, dict):
        raise ApiError(400, "expected a JSON object")
    return payload


def field(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ApiError(400, f"missing field: {key}")
    return value


def _status_payload(request: web.Request) -> dict[str, Any]:
    vault = request.app[VAULT]
    settings = request.app[SETTINGS]
    status = vault.status()
    return {
        "passphrase_set": status.passphrase_set,
        "unlocked": status.unlocked,
        "failed_attempts": status.failed_attempts,
        "retry_after": round(status.retry_after, 1),
        "kdf_n": status.kdf_n,
        "auto_lock_minutes": settings.auto_lock_minutes,
    }


async def get_vault(request: web.Request) -> web.Response:
    return web.json_response(_status_payload(request))


async def set_passphrase(request: web.Request) -> web.Response:
    payload = await body(request)
    params = await request.app[VAULT].set_passphrase(field(payload, "passphrase"))
    _LOGGER.info("Passphrase configured")
    return web.json_response({**_status_payload(request), "kdf_n": params.n})


async def change_passphrase(request: web.Request) -> web.Response:
    payload = await body(request)
    await request.app[VAULT].change_passphrase(field(payload, "current"), field(payload, "new"))
    return web.json_response(_status_payload(request))


async def remove_passphrase(request: web.Request) -> web.Response:
    payload = await body(request)
    moved = await request.app[VAULT].remove_passphrase(field(payload, "passphrase"))
    return web.json_response({**_status_payload(request), "migrated": moved})


async def unlock(request: web.Request) -> web.Response:
    payload = await body(request)
    await request.app[VAULT].unlock(field(payload, "passphrase"))
    return web.json_response(_status_payload(request))


async def lock(request: web.Request) -> web.Response:
    request.app[VAULT].lock()
    return web.json_response(_status_payload(request))


def _tier(value: object) -> Tier:
    try:
        return Tier(str(value))
    except ValueError as err:
        raise ApiError(400, "tier must be unattended or protected") from err


async def list_credentials(request: web.Request) -> web.Response:
    return web.json_response([c.as_dict() for c in request.app[CREDENTIALS].list()])


async def create_credential(request: web.Request) -> web.Response:
    payload = await body(request)
    store = request.app[CREDENTIALS]
    label = field(payload, "label")
    tier = _tier(payload.get("tier", Tier.UNATTENDED.value))
    kind = field(payload, "kind")

    if kind == CredentialKind.SSH.value:
        material = payload.get("private_key")
        if material is not None and not isinstance(material, str):
            raise ApiError(400, "private_key must be a string")
        credential = store.create_ssh(label, tier, material.encode("utf-8") if material else None)
    elif kind == CredentialKind.TOKEN.value:
        username = payload.get("username")
        credential = store.create_token(
            label,
            tier,
            field(payload, "token"),
            username if isinstance(username, str) and username else None,
        )
    else:
        raise ApiError(400, "kind must be ssh or token")

    return web.json_response(credential.as_dict(), status=201)


async def get_credential(request: web.Request) -> web.Response:
    return web.json_response(request.app[CREDENTIALS].get(request.match_info["cid"]).as_dict())


async def delete_credential(request: web.Request) -> web.Response:
    request.app[CREDENTIALS].delete(request.match_info["cid"])
    return web.json_response({"deleted": True})


async def rotate_credential(request: web.Request) -> web.Response:
    credential = request.app[CREDENTIALS].rotate_ssh(request.match_info["cid"])
    return web.json_response(credential.as_dict())


async def set_credential_tier(request: web.Request) -> web.Response:
    payload = await body(request)
    credential = request.app[CREDENTIALS].set_tier(
        request.match_info["cid"], _tier(field(payload, "tier"))
    )
    return web.json_response(credential.as_dict())


def register(app: web.Application) -> None:
    app.router.add_get("/api/vault", get_vault)
    app.router.add_post("/api/vault/passphrase", set_passphrase)
    app.router.add_put("/api/vault/passphrase", change_passphrase)
    app.router.add_delete("/api/vault/passphrase", remove_passphrase)
    app.router.add_post("/api/vault/unlock", unlock)
    app.router.add_post("/api/vault/lock", lock)

    app.router.add_get("/api/credentials", list_credentials)
    app.router.add_post("/api/credentials", create_credential)
    app.router.add_get("/api/credentials/{cid}", get_credential)
    app.router.add_delete("/api/credentials/{cid}", delete_credential)
    app.router.add_post("/api/credentials/{cid}/rotate", rotate_credential)
    app.router.add_put("/api/credentials/{cid}/tier", set_credential_tier)
