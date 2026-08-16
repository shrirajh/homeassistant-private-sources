"""Repository records and the add, install, update and remove flow."""

from __future__ import annotations

import json
import logging
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from .content import Category, ContentError, HacsManifest, Targets, detect, plan
from .credentials import CredentialStore
from .db import Database
from .gitops import Auth, Git, GitError, Ref
from .hass import HomeAssistant, HomeAssistantError
from .installer import Installer, InstallResult, RemovalResult

_LOGGER = logging.getLogger(__name__)

_SCP_LIKE = re.compile(r"^(?:(?P<user>[^@/]+)@)?(?P<host>[^:/]+):(?P<path>.+)$")
_NUMBERS = re.compile(r"\d+")
_PRERELEASE = re.compile(r"[-+._](alpha|beta|rc|dev|pre|snapshot)", re.IGNORECASE)


class RepositoryError(Exception):
    """Something is wrong with a repository record or its contents."""


class UnknownRepository(RepositoryError):
    """No repository with that identifier."""


def parse_url(url: str) -> tuple[str, str, str]:
    """Return host, owner and name for https, ssh and scp style git URLs."""
    raw = url.strip().rstrip("/")
    raw = raw.removesuffix(".git")
    if not raw:
        raise RepositoryError("repository URL is empty")

    if raw.startswith("file://"):
        # Local or mounted checkouts have no host, so name them after their path.
        parts = [p for p in urlsplit(raw).path.replace("\\", "/").split("/") if p]
        if not parts:
            raise RepositoryError(f"could not parse {url}")
        return "local", parts[-2] if len(parts) > 1 else "local", parts[-1]

    if "://" in raw:
        parsed = urlsplit(raw)
        host = parsed.hostname or ""
        parts = [p for p in parsed.path.split("/") if p]
    else:
        match = _SCP_LIKE.match(raw)
        if match is None:
            raise RepositoryError(f"could not parse {url}")
        host = match.group("host")
        parts = [p for p in match.group("path").split("/") if p]

    if not host or len(parts) < 2:
        raise RepositoryError(f"could not work out owner and repository from {url}")
    # GitLab allows nested groups, so everything before the last segment is the owner.
    return host, "/".join(parts[:-1]), parts[-1]


def version_key(tag: str) -> tuple:
    numbers = [int(n) for n in _NUMBERS.findall(tag.lstrip("vV"))[:4]]
    padded = (numbers + [0, 0, 0, 0])[:4]
    return (padded, 0 if _PRERELEASE.search(tag) else 1, tag)


def latest_tag(refs: list[Ref], *, allow_prerelease: bool = False) -> str | None:
    tags = [r.name for r in refs if r.kind == "tag"]
    if not allow_prerelease:
        stable = [t for t in tags if not _PRERELEASE.search(t)]
        tags = stable or tags
    return max(tags, key=version_key) if tags else None


def _compare_versions(left: str, right: str) -> int:
    a, b = version_key(left)[0], version_key(right)[0]
    return (a > b) - (a < b)


@dataclass(frozen=True)
class Repo:
    id: str
    url: str
    host: str
    owner: str
    name: str
    category: str
    credential_id: str | None
    ref_kind: str
    pinned_ref: str | None
    installed_ref: str | None
    installed_version: str | None
    available_version: str | None
    auto_update: bool
    hacs_json: str | None
    last_checked: str | None
    last_error: str | None

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.name}"

    @property
    def installed(self) -> bool:
        return self.installed_ref is not None

    @property
    def update_available(self) -> bool:
        if not self.installed or not self.available_version:
            return False
        return self.available_version != self.installed_version

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "url": self.url,
            "host": self.host,
            "owner": self.owner,
            "name": self.name,
            "slug": self.slug,
            "category": self.category,
            "credential_id": self.credential_id,
            "ref_kind": self.ref_kind,
            "pinned_ref": self.pinned_ref,
            "installed_ref": self.installed_ref,
            "installed_version": self.installed_version,
            "available_version": self.available_version,
            "auto_update": self.auto_update,
            "installed": self.installed,
            "update_available": self.update_available,
            "last_checked": self.last_checked,
            "last_error": self.last_error,
        }


_SELECT = """
SELECT id, url, host, owner, name, category, credential_id, ref_kind, pinned_ref,
       installed_ref, installed_version, available_version, auto_update, hacs_json,
       last_checked, last_error
  FROM repos
"""


def _to_repo(row) -> Repo:
    return Repo(
        id=row["id"],
        url=row["url"],
        host=row["host"],
        owner=row["owner"],
        name=row["name"],
        category=row["category"],
        credential_id=row["credential_id"],
        ref_kind=row["ref_kind"],
        pinned_ref=row["pinned_ref"],
        installed_ref=row["installed_ref"],
        installed_version=row["installed_version"],
        available_version=row["available_version"],
        auto_update=bool(row["auto_update"]),
        hacs_json=row["hacs_json"],
        last_checked=row["last_checked"],
        last_error=row["last_error"],
    )


class RepositoryStore:
    def __init__(
        self,
        db: Database,
        credentials: CredentialStore,
        git: Git,
        installer: Installer,
        hass: HomeAssistant,
        targets: Targets,
    ) -> None:
        self._db = db
        self._credentials = credentials
        self._git = git
        self._installer = installer
        self._hass = hass
        self._targets = targets

    def list(self) -> list[Repo]:
        return [_to_repo(row) for row in self._db.all(f"{_SELECT} ORDER BY owner, name")]

    def get(self, repo_id: str) -> Repo:
        row = self._db.one(f"{_SELECT} WHERE id = ?", (repo_id,))
        if row is None:
            raise UnknownRepository(f"no repository {repo_id}")
        return _to_repo(row)

    async def add(
        self,
        url: str,
        *,
        credential_id: str | None = None,
        category: Category | None = None,
        ref_kind: str = "tag",
        pinned_ref: str | None = None,
        auto_update: bool = False,
    ) -> Repo:
        host, owner, name = parse_url(url)
        if self._db.one("SELECT 1 FROM repos WHERE url = ?", (url,)):
            raise RepositoryError("that repository is already tracked")

        repo_id = uuid4().hex
        auth = self._auth_for(credential_id)
        await self._git.mirror(repo_id, url, auth)

        ref = pinned_ref or await self._pick_ref(repo_id, ref_kind, None)
        manifest = await self._manifest(repo_id, ref)
        resolved = category or detect(await self._git.ls_tree(repo_id, ref), manifest)
        if resolved is None:
            self._git.forget_mirror(repo_id)
            raise ContentError(
                "could not work out what this repository contains, choose a category explicitly"
            )

        self._db.execute(
            """INSERT INTO repos
                   (id, url, host, owner, name, category, credential_id, ref_kind, pinned_ref,
                    auto_update, hacs_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                repo_id,
                url,
                host,
                owner,
                name,
                resolved.value,
                credential_id,
                ref_kind,
                pinned_ref,
                int(auto_update),
                json.dumps(manifest.__dict__, default=str),
            ),
        )
        self._touch_available(repo_id, await self._git.local_refs(repo_id), ref_kind)
        _LOGGER.info("Tracking %s/%s as %s", owner, name, resolved.value)
        return self.get(repo_id)

    async def refresh(self, repo_id: str) -> Repo:
        repo = self.get(repo_id)
        try:
            await self._git.mirror(repo_id, repo.url, self._auth_for(repo.credential_id))
            refs = await self._git.local_refs(repo_id)
        except (GitError, RepositoryError) as err:
            self._db.execute(
                "UPDATE repos SET last_checked = datetime('now'), last_error = ? WHERE id = ?",
                (str(err), repo_id),
            )
            raise
        self._touch_available(repo_id, refs, repo.ref_kind)
        return self.get(repo_id)

    async def available_refs(self, repo_id: str) -> list[Ref]:
        return await self._git.local_refs(repo_id)

    async def install(self, repo_id: str, ref: str | None = None) -> InstallResult:
        repo = self.get(repo_id)
        auth = self._auth_for(repo.credential_id)
        await self._git.mirror(repo_id, repo.url, auth)

        target = ref or repo.pinned_ref or await self._pick_ref(repo_id, repo.ref_kind, repo)
        sha = await self._git.resolve(repo_id, target)
        manifest = await self._manifest(repo_id, target)
        await self._check_core_version(manifest)

        category = Category(repo.category)
        with tempfile.TemporaryDirectory(prefix="psm-install-") as tmp:
            staging = Path(tmp) / "tree"
            await self._git.export(repo_id, target, staging)
            layout = plan(category, staging, repo.name, manifest, self._targets)
            result = self._installer.apply(repo_id, layout)

        version = target if repo.ref_kind == "tag" else f"{target}@{sha[:7]}"
        await self._after_install(layout.resource_url, layout.addon_slug, version)

        self._db.execute(
            """UPDATE repos
                  SET installed_ref = ?, installed_version = ?, available_version = ?,
                      last_error = NULL, updated_at = datetime('now')
                WHERE id = ?""",
            (sha, version, version, repo_id),
        )
        self._touch_available(repo_id, await self._git.local_refs(repo_id), repo.ref_kind)
        _LOGGER.info("Installed %s at %s", repo.slug, version)
        return result

    async def uninstall(self, repo_id: str, *, force: bool = False) -> RemovalResult:
        repo = self.get(repo_id)
        result = self._installer.remove(repo_id, force=force)
        if not result.clean:
            return result

        if repo.category == Category.PLUGIN.value:
            await self._drop_resource(repo)
        if repo.category == Category.ADDON.value:
            await self._safe(self._hass.reload_store())

        self._db.execute(
            """UPDATE repos
                  SET installed_ref = NULL, installed_version = NULL, updated_at = datetime('now')
                WHERE id = ?""",
            (repo_id,),
        )
        return result

    async def delete(self, repo_id: str, *, force: bool = False) -> RemovalResult:
        result = await self.uninstall(repo_id, force=force)
        if result.clean:
            self._git.forget_mirror(repo_id)
            self._db.execute("DELETE FROM repos WHERE id = ?", (repo_id,))
        return result

    def update_settings(
        self,
        repo_id: str,
        *,
        credential_id: str | None = None,
        ref_kind: str | None = None,
        pinned_ref: str | None = None,
        auto_update: bool | None = None,
        category: Category | None = None,
        clear_pin: bool = False,
    ) -> Repo:
        repo = self.get(repo_id)
        self._db.execute(
            """UPDATE repos
                  SET credential_id = ?, ref_kind = ?, pinned_ref = ?, auto_update = ?,
                      category = ?, updated_at = datetime('now')
                WHERE id = ?""",
            (
                credential_id if credential_id is not None else repo.credential_id,
                ref_kind or repo.ref_kind,
                None if clear_pin else (pinned_ref if pinned_ref is not None else repo.pinned_ref),
                int(repo.auto_update if auto_update is None else auto_update),
                (category.value if category else repo.category),
                repo_id,
            ),
        )
        return self.get(repo_id)

    def _auth_for(self, credential_id: str | None) -> Auth | None:
        if not credential_id:
            return None
        credential = self._credentials.get(credential_id)
        return Auth(
            kind=credential.kind,
            secret=self._credentials.secret(credential_id),
            username=credential.username,
        )

    def auth_for_repo(self, repo: Repo) -> Auth | None:
        return self._auth_for(repo.credential_id)

    async def _pick_ref(self, repo_id: str, ref_kind: str, repo: Repo | None) -> str:
        refs = await self._git.local_refs(repo_id)
        if ref_kind == "tag":
            newest = latest_tag(refs)
            if newest:
                return newest
            _LOGGER.info("No tags found, falling back to the default branch")
        if repo is not None and repo.pinned_ref:
            return repo.pinned_ref
        return await self._git.default_branch(repo_id)

    async def _manifest(self, repo_id: str, ref: str) -> HacsManifest:
        try:
            raw = await self._git.show(repo_id, ref, "hacs.json")
        except GitError:
            return HacsManifest()
        return HacsManifest.parse(raw)

    async def _check_core_version(self, manifest: HacsManifest) -> None:
        if not manifest.homeassistant or not self._hass.available:
            return
        current = await self._hass.core_version()
        if current and _compare_versions(current, manifest.homeassistant) < 0:
            raise RepositoryError(
                f"needs Home Assistant {manifest.homeassistant}, this system runs {current}"
            )

    async def _after_install(
        self, resource_url: str | None, addon_slug: str | None, version: str
    ) -> None:
        if resource_url:
            await self._safe(self._hass.ensure_resource(f"{resource_url}?v={version}"))
        if addon_slug:
            await self._safe(self._hass.reload_store())

    async def _drop_resource(self, repo: Repo) -> None:
        url = f"/local/community/{repo.name}/"
        for item in await self._resources():
            if str(item.get("url", "")).startswith(url):
                await self._safe(self._hass.remove_resource(str(item["url"])))

    async def _resources(self) -> list[dict]:
        try:
            return await self._hass.lovelace_resources()
        except HomeAssistantError as err:
            _LOGGER.warning("Could not read Lovelace resources: %s", err)
            return []

    async def _safe(self, awaitable) -> None:
        try:
            await awaitable
        except HomeAssistantError as err:
            _LOGGER.warning("Home Assistant call failed: %s", err)

    def _touch_available(self, repo_id: str, refs: list[Ref], ref_kind: str) -> None:
        available = latest_tag(refs) if ref_kind == "tag" else None
        if available is None:
            row = self._db.one("SELECT installed_version FROM repos WHERE id = ?", (repo_id,))
            available = row["installed_version"] if row else None
        self._db.execute(
            """UPDATE repos
                  SET available_version = ?, last_checked = datetime('now'), last_error = NULL
                WHERE id = ?""",
            (available, repo_id),
        )
