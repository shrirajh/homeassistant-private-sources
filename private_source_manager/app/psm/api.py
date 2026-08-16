"""JSON API handlers."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiohttp import web

from .content import Category, ContentError
from .context import CREDENTIALS, GIT, HASS, REPOS, SETTINGS, VAULT
from .credentials import CredentialInUse, CredentialKind, UnknownCredential
from .gitops import Auth, GitError, HostKeyUnknown
from .hass import HomeAssistantError
from .hosts import HostError
from .repos import RepositoryError, UnknownRepository
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
    except UnknownRepository as err:
        return web.json_response({"error": str(err), "code": "UnknownRepository"}, status=404)
    except ContentError as err:
        return web.json_response({"error": str(err), "code": "ContentError"}, status=400)
    except RepositoryError as err:
        return web.json_response({"error": str(err), "code": "RepositoryError"}, status=400)
    except HomeAssistantError as err:
        return web.json_response({"error": str(err), "code": "HomeAssistantError"}, status=502)
    except HostError as err:
        return web.json_response({"error": str(err), "code": "HostError"}, status=502)
    except HostKeyUnknown as err:
        return web.json_response(
            {"error": str(err), "code": "HostKeyUnknown", "detail": err.stderr}, status=409
        )
    except GitError as err:
        return web.json_response(
            {"error": str(err), "code": "GitError", "detail": err.stderr}, status=400
        )
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


def auth_for(request: web.Request, credential_id: str | None) -> Auth | None:
    """Decrypt a credential for the git layer. Raises if the tier is unavailable."""
    if not credential_id:
        return None
    store = request.app[CREDENTIALS]
    credential = store.get(credential_id)
    return Auth(
        kind=credential.kind,
        secret=store.secret(credential_id),
        username=credential.username,
    )


async def test_credential(request: web.Request) -> web.Response:
    payload = await body(request)
    url = field(payload, "url")
    auth = auth_for(request, request.match_info["cid"])

    refs = await request.app[GIT].ls_remote(url, auth)
    return web.json_response(
        {
            "ok": True,
            "tags": sorted({r.name for r in refs if r.kind == "tag"}),
            "branches": sorted({r.name for r in refs if r.kind == "branch"}),
        }
    )


async def scan_host(request: web.Request) -> web.Response:
    payload = await body(request)
    host = field(payload, "host")
    try:
        port = int(payload.get("port", 22))
    except (TypeError, ValueError) as err:
        raise ApiError(400, "port must be a number") from err

    keys = await request.app[GIT].scan_host(host, port)
    if not keys:
        raise ApiError(404, f"no host keys returned by {host}")
    return web.json_response({"host": host, "port": port, "keys": keys})


async def trust_host(request: web.Request) -> web.Response:
    payload = await body(request)
    lines = payload.get("lines")
    if not isinstance(lines, list) or not all(isinstance(line, str) for line in lines):
        raise ApiError(400, "lines must be a list of strings")
    return web.json_response({"added": request.app[GIT].trust_host(lines)})


def _category(value: object) -> Category | None:
    if value in (None, ""):
        return None
    try:
        return Category(str(value))
    except ValueError as err:
        raise ApiError(400, f"unknown category {value}") from err


def _optional_bool(payload: dict[str, Any], key: str) -> bool | None:
    value = payload.get(key)
    return None if value is None else bool(value)


async def list_repos(request: web.Request) -> web.Response:
    return web.json_response([r.as_dict() for r in request.app[REPOS].list()])


async def add_repo(request: web.Request) -> web.Response:
    payload = await body(request)
    repo = await request.app[REPOS].add(
        field(payload, "url"),
        credential_id=payload.get("credential_id") or None,
        category=_category(payload.get("category")),
        ref_kind=str(payload.get("ref_kind") or "tag"),
        pinned_ref=payload.get("pinned_ref") or None,
        auto_update=bool(payload.get("auto_update", False)),
    )
    return web.json_response(repo.as_dict(), status=201)


async def get_repo(request: web.Request) -> web.Response:
    return web.json_response(request.app[REPOS].get(request.match_info["rid"]).as_dict())


async def patch_repo(request: web.Request) -> web.Response:
    payload = await body(request)
    repo = request.app[REPOS].update_settings(
        request.match_info["rid"],
        credential_id=payload.get("credential_id"),
        ref_kind=payload.get("ref_kind"),
        pinned_ref=payload.get("pinned_ref"),
        auto_update=_optional_bool(payload, "auto_update"),
        category=_category(payload.get("category")),
        clear_pin=bool(payload.get("clear_pin", False)),
    )
    return web.json_response(repo.as_dict())


async def repo_refs(request: web.Request) -> web.Response:
    refs = await request.app[REPOS].available_refs(request.match_info["rid"])
    return web.json_response([r.as_dict() for r in refs])


async def repo_releases(request: web.Request) -> web.Response:
    releases = await request.app[REPOS].releases(request.match_info["rid"])
    return web.json_response([r.as_dict() for r in releases])


async def refresh_repo(request: web.Request) -> web.Response:
    return web.json_response(
        (await request.app[REPOS].refresh(request.match_info["rid"])).as_dict()
    )


async def install_repo(request: web.Request) -> web.Response:
    payload = await body(request) if request.can_read_body else {}
    store = request.app[REPOS]
    result = await store.install(request.match_info["rid"], payload.get("ref") or None)
    return web.json_response(
        {
            "files": result.files,
            "domain": result.domain,
            "resource_url": result.resource_url,
            "addon_slug": result.addon_slug,
            "repo": store.get(request.match_info["rid"]).as_dict(),
        }
    )


async def uninstall_repo(request: web.Request) -> web.Response:
    payload = await body(request) if request.can_read_body else {}
    result = await request.app[REPOS].uninstall(
        request.match_info["rid"], force=bool(payload.get("force", False))
    )
    return web.json_response(
        {"removed": result.removed, "missing": result.missing, "modified": result.modified},
        status=200 if result.clean else 409,
    )


async def delete_repo(request: web.Request) -> web.Response:
    force = request.query.get("force") in ("1", "true", "yes")
    result = await request.app[REPOS].delete(request.match_info["rid"], force=force)
    return web.json_response(
        {"deleted": result.clean, "modified": result.modified},
        status=200 if result.clean else 409,
    )


async def restart_core(request: web.Request) -> web.Response:
    await request.app[HASS].restart_core()
    return web.json_response({"restarting": True})


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
    app.router.add_post("/api/credentials/{cid}/test", test_credential)

    app.router.add_post("/api/hosts/scan", scan_host)
    app.router.add_post("/api/hosts/trust", trust_host)

    app.router.add_get("/api/repos", list_repos)
    app.router.add_post("/api/repos", add_repo)
    app.router.add_get("/api/repos/{rid}", get_repo)
    app.router.add_patch("/api/repos/{rid}", patch_repo)
    app.router.add_delete("/api/repos/{rid}", delete_repo)
    app.router.add_get("/api/repos/{rid}/refs", repo_refs)
    app.router.add_get("/api/repos/{rid}/releases", repo_releases)
    app.router.add_post("/api/repos/{rid}/refresh", refresh_repo)
    app.router.add_post("/api/repos/{rid}/install", install_repo)
    app.router.add_post("/api/repos/{rid}/uninstall", uninstall_repo)

    app.router.add_post("/api/core/restart", restart_core)
