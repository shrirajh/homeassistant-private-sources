"""Host specific release metadata.

Plain git only yields tags. The GitHub and GitLab APIs additionally give release
names, changelog bodies, prerelease flags and downloadable assets, which is what
zip_release repositories need. Hosts without an adapter degrade to tags only.

API access needs a token. A repository authenticated with an SSH deploy key gets
git access but no API access, so it also degrades to tags only.
"""

from __future__ import annotations

import logging
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import aiohttp

from .credentials import CredentialKind
from .gitops import Auth

_LOGGER = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=120)
_PER_PAGE = 30

GITHUB = "github"
GITLAB = "gitlab"
GENERIC = "generic"


class HostError(Exception):
    """The host API refused or could not be reached."""


@dataclass(frozen=True)
class Asset:
    name: str
    url: str
    size: int = 0

    def as_dict(self) -> dict[str, object]:
        return {"name": self.name, "url": self.url, "size": self.size}


@dataclass(frozen=True)
class Release:
    tag: str
    name: str | None = None
    body: str | None = None
    prerelease: bool = False
    published_at: str | None = None
    assets: tuple[Asset, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "tag": self.tag,
            "name": self.name,
            "body": self.body,
            "prerelease": self.prerelease,
            "published_at": self.published_at,
            "assets": [a.as_dict() for a in self.assets],
        }


def kind_for(host: str) -> str:
    lowered = host.lower()
    if lowered == "github.com":
        return GITHUB
    if lowered == "gitlab.com" or "gitlab" in lowered:
        return GITLAB
    return GENERIC


def api_root(host: str, kind: str) -> str:
    if kind == GITHUB:
        return (
            "https://api.github.com" if host.lower() == "github.com" else f"https://{host}/api/v3"
        )
    if kind == GITLAB:
        return f"https://{host}/api/v4"
    raise HostError(f"{host} has no API adapter")


def _headers(kind: str, auth: Auth | None) -> dict[str, str]:
    base = {"Accept": "application/json"}
    if kind == GITHUB:
        base = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if auth is None or auth.kind is not CredentialKind.TOKEN:
        return base
    token = auth.secret.decode("utf-8")
    if kind == GITHUB:
        return {**base, "Authorization": f"Bearer {token}"}
    return {**base, "PRIVATE-TOKEN": token}


def extract_zip(archive: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    root = dest.resolve()
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            target = (dest / member.filename).resolve()
            if target != root and not target.is_relative_to(root):
                raise HostError(f"archive tries to escape the target directory: {member.filename}")
        bundle.extractall(dest)


class Hosts:
    def __init__(self, api_root_override: str | None = None) -> None:
        self._session: aiohttp.ClientSession | None = None
        self._override = api_root_override

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

    def supports_api(self, host: str) -> bool:
        return kind_for(host) != GENERIC

    async def releases(
        self, host: str, owner: str, name: str, auth: Auth | None = None
    ) -> list[Release]:
        kind = kind_for(host)
        if kind == GENERIC:
            return []
        root = self._override or api_root(host, kind)
        if kind == GITHUB:
            path = f"{root}/repos/{owner}/{name}/releases?per_page={_PER_PAGE}"
            payload = await self._get_json(path, _headers(kind, auth))
            return [_github_release(item) for item in payload if isinstance(item, dict)]

        project = quote(f"{owner}/{name}", safe="")
        path = f"{root}/projects/{project}/releases?per_page={_PER_PAGE}"
        payload = await self._get_json(path, _headers(kind, auth))
        return [_gitlab_release(item) for item in payload if isinstance(item, dict)]

    async def download(self, host: str, url: str, dest: Path, auth: Auth | None = None) -> Path:
        kind = kind_for(host)
        headers = _headers(kind, auth)
        if kind == GITHUB:
            headers = {**headers, "Accept": "application/octet-stream"}

        session = self._ensure_session()
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            async with session.get(url, headers=headers) as response:
                if response.status >= 400:
                    raise HostError(f"download failed: {response.status}")
                with dest.open("wb") as handle:
                    async for chunk in response.content.iter_chunked(1 << 16):
                        handle.write(chunk)
        except aiohttp.ClientError as err:
            raise HostError(f"download failed: {err}") from err
        return dest

    def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=_TIMEOUT)
        return self._session

    async def _get_json(self, url: str, headers: dict[str, str]) -> list:
        session = self._ensure_session()
        try:
            async with session.get(url, headers=headers) as response:
                if response.status in (401, 403):
                    if response.headers.get("X-RateLimit-Remaining") == "0":
                        raise HostError("API rate limit reached, try again later")
                    raise HostError("API rejected the credentials for this repository")
                if response.status == 404:
                    return []
                if response.status >= 400:
                    raise HostError(f"API returned {response.status}")
                payload = await response.json(content_type=None)
        except aiohttp.ClientError as err:
            raise HostError(f"API request failed: {err}") from err
        return payload if isinstance(payload, list) else []


def _github_release(item: dict) -> Release:
    assets = tuple(
        Asset(
            name=str(a.get("name", "")),
            url=str(a.get("url", "")),
            size=int(a.get("size", 0) or 0),
        )
        for a in item.get("assets", [])
        if isinstance(a, dict)
    )
    return Release(
        tag=str(item.get("tag_name", "")),
        name=item.get("name"),
        body=item.get("body"),
        prerelease=bool(item.get("prerelease", False)),
        published_at=item.get("published_at"),
        assets=assets,
    )


def _gitlab_release(item: dict) -> Release:
    links = (item.get("assets") or {}).get("links") or []
    assets = tuple(
        Asset(name=str(a.get("name", "")), url=str(a.get("url", "")))
        for a in links
        if isinstance(a, dict)
    )
    return Release(
        tag=str(item.get("tag_name", "")),
        name=item.get("name"),
        body=item.get("description"),
        prerelease=bool(item.get("upcoming_release", False)),
        published_at=item.get("released_at"),
        assets=assets,
    )
