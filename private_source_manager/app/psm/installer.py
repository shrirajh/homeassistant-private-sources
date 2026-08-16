"""Transactional installation with a tracked file manifest."""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from .content import Plan, Targets
from .db import Database

_LOGGER = logging.getLogger(__name__)

_CHUNK = 1 << 16


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class InstallResult:
    files: int
    resource_url: str | None = None
    domain: str | None = None
    addon_slug: str | None = None


@dataclass(frozen=True)
class RemovalResult:
    removed: int
    modified: list[str]
    missing: int

    @property
    def clean(self) -> bool:
        return not self.modified


def _protected_directories(targets: Targets) -> set[Path]:
    config = targets.ha_config_dir
    return {
        p
        for p in (
            config,
            config / "custom_components",
            config / "www",
            config / "www" / "community",
            config / "themes",
            config / "python_scripts",
            config / "appdaemon",
            config / "appdaemon" / "apps",
            targets.addons_dir,
        )
    }


class Installer:
    def __init__(self, db: Database, targets: Targets) -> None:
        self._db = db
        self._protected = _protected_directories(targets)

    def apply(self, repo_id: str, plan: Plan) -> InstallResult:
        if plan.swap_root is not None:
            self._swap(plan)
        else:
            self._write_each(plan)

        self._record(repo_id, plan)
        _LOGGER.info("Installed %d files for %s", len(plan.files), repo_id)
        return InstallResult(
            files=len(plan.files),
            resource_url=plan.resource_url,
            domain=plan.domain,
            addon_slug=plan.addon_slug,
        )

    def remove(self, repo_id: str, *, force: bool = False) -> RemovalResult:
        rows = self._db.all(
            "SELECT path, sha256 FROM installed_files WHERE repo_id = ?", (repo_id,)
        )
        removed = 0
        missing = 0
        modified: list[str] = []
        parents: set[Path] = set()

        for row in rows:
            path = Path(row["path"])
            if not path.is_file():
                missing += 1
                continue
            if not force and sha256_file(path) != row["sha256"]:
                modified.append(str(path))
                continue
            path.unlink()
            removed += 1
            parents.add(path.parent)

        for directory in sorted(parents, key=lambda p: len(p.parts), reverse=True):
            self._prune(directory)

        if not modified:
            self._db.execute("DELETE FROM installed_files WHERE repo_id = ?", (repo_id,))

        _LOGGER.info(
            "Removed %d files for %s, %d missing, %d locally modified",
            removed,
            repo_id,
            missing,
            len(modified),
        )
        return RemovalResult(removed=removed, modified=modified, missing=missing)

    def tracked(self, repo_id: str) -> list[str]:
        return [
            row["path"]
            for row in self._db.all(
                "SELECT path FROM installed_files WHERE repo_id = ? ORDER BY path", (repo_id,)
            )
        ]

    def _swap(self, plan: Plan) -> None:
        """Build the new tree beside the old one, then exchange them with two renames."""
        root = plan.swap_root
        parent = root.parent
        parent.mkdir(parents=True, exist_ok=True)

        staging = parent / f".psm-new-{uuid4().hex}"
        backup = parent / f".psm-old-{uuid4().hex}"
        try:
            for source, dest in plan.files:
                target = staging / dest.relative_to(root)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)

            self._preserve(root, staging, plan.persistent_directory)

            had_previous = root.exists()
            if had_previous:
                os.replace(root, backup)
            try:
                os.replace(staging, root)
            except OSError:
                if had_previous:
                    os.replace(backup, root)
                raise
        finally:
            shutil.rmtree(staging, ignore_errors=True)
            shutil.rmtree(backup, ignore_errors=True)

    def _preserve(self, root: Path, staging: Path, relative: str | None) -> None:
        if not relative:
            return
        source = root / relative
        if not source.is_dir():
            return
        target = staging / relative
        shutil.rmtree(target, ignore_errors=True)
        shutil.copytree(source, target)
        _LOGGER.info("Preserved %s across the upgrade", relative)

    def _write_each(self, plan: Plan) -> None:
        for source, dest in plan.files:
            dest.parent.mkdir(parents=True, exist_ok=True)
            temporary = dest.parent / f".psm-{uuid4().hex}"
            shutil.copy2(source, temporary)
            os.replace(temporary, dest)

    def _record(self, repo_id: str, plan: Plan) -> None:
        rows = [(repo_id, str(dest), sha256_file(dest)) for _, dest in plan.files]
        with self._db.transaction() as conn:
            conn.execute("DELETE FROM installed_files WHERE repo_id = ?", (repo_id,))
            conn.executemany(
                "INSERT INTO installed_files (repo_id, path, sha256) VALUES (?, ?, ?)", rows
            )

    def _prune(self, directory: Path) -> None:
        current = directory
        while current.is_dir() and current not in self._protected:
            if any(current.iterdir()):
                return
            current.rmdir()
            current = current.parent
