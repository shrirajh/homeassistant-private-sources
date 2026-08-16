"""GitHub and GitLab release adapters."""

from __future__ import annotations

import zipfile
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from psm.credentials import CredentialKind
from psm.gitops import Auth
from psm.hosts import (
    GENERIC,
    GITHUB,
    GITLAB,
    HostError,
    Hosts,
    _headers,
    api_root,
    extract_zip,
    kind_for,
)

_GITHUB_PAYLOAD = [
    {
        "tag_name": "v2.0.0",
        "name": "Two point oh",
        "body": "Big changes",
        "prerelease": False,
        "published_at": "2026-01-02T03:04:05Z",
        "assets": [{"name": "demo.zip", "url": "https://assets.invalid/1", "size": 1234}],
    },
    {"tag_name": "v2.1.0-rc1", "prerelease": True, "assets": []},
]

_GITLAB_PAYLOAD = [
    {
        "tag_name": "v3.0.0",
        "name": "Three",
        "description": "GitLab changelog",
        "released_at": "2026-02-03T00:00:00Z",
        "assets": {"links": [{"name": "bundle.zip", "url": "https://assets.invalid/2"}]},
    }
]


@pytest.fixture
async def api() -> AsyncIterator[tuple[TestServer, dict]]:
    state: dict = {"status": 200, "payload": [], "headers": {}, "seen": []}

    async def handler(request: web.Request) -> web.Response:
        state["seen"].append(request.raw_path)
        state["auth"] = dict(request.headers)
        if state["status"] >= 400:
            return web.json_response({}, status=state["status"], headers=state["headers"])
        return web.json_response(state["payload"])

    app = web.Application()
    app.router.add_get("/{tail:.*}", handler)
    server = TestServer(app)
    await server.start_server()
    yield server, state
    await server.close()


@pytest.fixture
async def hosts(api: tuple[TestServer, dict]) -> AsyncIterator[Hosts]:
    server, _ = api
    instance = Hosts(api_root_override=str(server.make_url("")).rstrip("/"))
    yield instance
    await instance.close()


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("github.com", GITHUB),
        ("GitHub.com", GITHUB),
        ("gitlab.com", GITLAB),
        ("gitlab.example.org", GITLAB),
        ("gitea.lan", GENERIC),
        ("git.example.com", GENERIC),
    ],
)
def test_kind_for(host: str, expected: str) -> None:
    assert kind_for(host) == expected


def test_api_root() -> None:
    assert api_root("github.com", GITHUB) == "https://api.github.com"
    assert api_root("github.example.com", GITHUB) == "https://github.example.com/api/v3"
    assert api_root("gitlab.com", GITLAB) == "https://gitlab.com/api/v4"
    with pytest.raises(HostError):
        api_root("gitea.lan", GENERIC)


def test_headers_carry_tokens_only_for_token_credentials() -> None:
    token = Auth(kind=CredentialKind.TOKEN, secret=b"ghp_secret")
    ssh = Auth(kind=CredentialKind.SSH, secret=b"key")

    assert _headers(GITHUB, token)["Authorization"] == "Bearer ghp_secret"
    assert _headers(GITLAB, token)["PRIVATE-TOKEN"] == "ghp_secret"
    # A deploy key cannot authenticate to a REST API.
    assert "Authorization" not in _headers(GITHUB, ssh)
    assert "PRIVATE-TOKEN" not in _headers(GITLAB, ssh)
    assert "Authorization" not in _headers(GITHUB, None)


def test_generic_hosts_have_no_api() -> None:
    assert Hosts().supports_api("gitea.lan") is False
    assert Hosts().supports_api("github.com") is True


async def test_github_releases(hosts: Hosts, api: tuple[TestServer, dict]) -> None:
    _, state = api
    state["payload"] = _GITHUB_PAYLOAD

    releases = await hosts.releases("github.com", "me", "thing")

    assert [r.tag for r in releases] == ["v2.0.0", "v2.1.0-rc1"]
    assert releases[0].name == "Two point oh"
    assert releases[0].body == "Big changes"
    assert releases[0].prerelease is False
    assert releases[1].prerelease is True
    assert releases[0].assets[0].name == "demo.zip"
    assert releases[0].assets[0].size == 1234
    assert "/repos/me/thing/releases" in state["seen"][0]


async def test_gitlab_releases_url_encodes_nested_groups(
    hosts: Hosts, api: tuple[TestServer, dict]
) -> None:
    _, state = api
    state["payload"] = _GITLAB_PAYLOAD

    releases = await hosts.releases("gitlab.com", "group/sub", "thing")

    assert releases[0].tag == "v3.0.0"
    assert releases[0].body == "GitLab changelog"
    assert releases[0].assets[0].name == "bundle.zip"
    assert "group%2Fsub%2Fthing" in state["seen"][0]


async def test_generic_host_returns_nothing(hosts: Hosts) -> None:
    assert await hosts.releases("gitea.lan", "me", "thing") == []


async def test_missing_project_is_empty(hosts: Hosts, api: tuple[TestServer, dict]) -> None:
    _, state = api
    state["status"] = 404
    assert await hosts.releases("github.com", "me", "thing") == []


async def test_rejected_credentials(hosts: Hosts, api: tuple[TestServer, dict]) -> None:
    _, state = api
    state["status"] = 401
    with pytest.raises(HostError, match="rejected"):
        await hosts.releases("github.com", "me", "thing")


async def test_rate_limit_is_reported_clearly(hosts: Hosts, api: tuple[TestServer, dict]) -> None:
    _, state = api
    state["status"] = 403
    state["headers"] = {"X-RateLimit-Remaining": "0"}
    with pytest.raises(HostError, match="rate limit"):
        await hosts.releases("github.com", "me", "thing")


async def test_server_error(hosts: Hosts, api: tuple[TestServer, dict]) -> None:
    _, state = api
    state["status"] = 500
    with pytest.raises(HostError, match="500"):
        await hosts.releases("github.com", "me", "thing")


async def test_token_is_sent(hosts: Hosts, api: tuple[TestServer, dict]) -> None:
    _, state = api
    state["payload"] = _GITHUB_PAYLOAD
    auth = Auth(kind=CredentialKind.TOKEN, secret=b"ghp_secret")

    await hosts.releases("github.com", "me", "thing", auth)

    assert state["auth"]["Authorization"] == "Bearer ghp_secret"


async def test_download(hosts: Hosts, api: tuple[TestServer, dict], tmp_path: Path) -> None:
    server, state = api
    state["payload"] = {"hello": "world"}

    dest = await hosts.download("github.com", str(server.make_url("/asset")), tmp_path / "a.json")

    assert dest.is_file()
    assert b"hello" in dest.read_bytes()


async def test_download_failure(hosts: Hosts, api: tuple[TestServer, dict], tmp_path: Path) -> None:
    server, state = api
    state["status"] = 500
    with pytest.raises(HostError, match="download failed"):
        await hosts.download("github.com", str(server.make_url("/asset")), tmp_path / "a.zip")


def test_extract_zip(tmp_path: Path) -> None:
    archive = tmp_path / "bundle.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("custom_components/demo/manifest.json", '{"domain": "demo"}')

    dest = tmp_path / "out"
    extract_zip(archive, dest)

    assert (dest / "custom_components" / "demo" / "manifest.json").is_file()


def test_extract_zip_refuses_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("../../escaped.txt", "pwned")

    with pytest.raises(HostError, match="escape"):
        extract_zip(archive, tmp_path / "out")

    assert not (tmp_path.parent / "escaped.txt").exists()
