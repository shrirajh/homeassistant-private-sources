"""Update sweeps, auto updates and notification behaviour."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from psm.content import Targets
from psm.credentials import CredentialStore
from psm.db import Database
from psm.gitops import Git
from psm.hass import HomeAssistant
from psm.hosts import Hosts
from psm.installer import Installer
from psm.keystore import LocalKeystore
from psm.repos import RepositoryStore
from psm.updater import LOCKED_NOTIFICATION, UPDATES_NOTIFICATION, Updater
from psm.vault import Tier, Vault

from conftest import make_settings

PASSPHRASE = "correct horse battery"

_GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.invalid",
}


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, env=_GIT_ENV)


class FakeHass(HomeAssistant):
    def __init__(self) -> None:
        super().__init__("fake-token")
        self.notifications: list[tuple[str, str, str]] = []
        self.dismissed: list[str] = []

    async def notify(self, title: str, message: str, notification_id: str) -> None:
        self.notifications.append((notification_id, title, message))

    async def dismiss(self, notification_id: str) -> None:
        self.dismissed.append(notification_id)

    async def ensure_resource(self, url: str) -> str:
        return "created"

    async def reload_store(self) -> None:
        return None

    async def core_version(self) -> str | None:
        return None

    def ids(self) -> list[str]:
        return [n[0] for n in self.notifications]


@dataclass
class Harness:
    repos: RepositoryStore
    credentials: CredentialStore
    vault: Vault
    hass: FakeHass
    updater: Updater
    targets: Targets


@pytest.fixture
def harness(tmp_path: Path) -> Harness:
    keystore_dir = tmp_path / "keystore"
    keystore_dir.mkdir()
    db = Database(tmp_path / "psm.db")
    vault = Vault(db, LocalKeystore(keystore_dir))
    vault.start()

    targets = Targets(ha_config_dir=tmp_path / "homeassistant", addons_dir=tmp_path / "addons")
    credentials = CredentialStore(db, vault)
    hass = FakeHass()
    repos = RepositoryStore(
        db,
        credentials,
        Git(tmp_path / "cache", tmp_path / "known_hosts"),
        Installer(db, targets),
        hass,
        targets,
        Hosts(),
    )
    settings = make_settings(tmp_path)
    return Harness(
        repos, credentials, vault, hass, Updater(repos, credentials, vault, hass, settings), targets
    )


@pytest.fixture
def source(tmp_path: Path) -> Path:
    repo = tmp_path / "source"
    demo = repo / "custom_components" / "demo"
    demo.mkdir(parents=True)
    (demo / "manifest.json").write_text('{"domain": "demo"}', encoding="utf-8")
    (demo / "sensor.py").write_text("VERSION = '1.0.0'", encoding="utf-8")
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "initial")
    _git(repo, "tag", "v1.0.0")
    return repo


def _release(repo: Path, version: str) -> None:
    (repo / "custom_components" / "demo" / "sensor.py").write_text(
        f"VERSION = '{version}'", encoding="utf-8"
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", version)
    _git(repo, "tag", f"v{version}")


async def test_empty_sweep(harness: Harness) -> None:
    summary = await harness.updater.run_once()

    assert summary.checked == 0
    assert summary.updates == []
    assert UPDATES_NOTIFICATION in harness.hass.dismissed


async def test_detects_available_update_and_notifies(harness: Harness, source: Path) -> None:
    repo = await harness.repos.add(source.as_uri())
    await harness.repos.install(repo.id)
    _release(source, "1.1.0")

    summary = await harness.updater.run_once()

    assert summary.checked == 1
    assert summary.updates == [f"{repo.slug} v1.1.0"]
    assert summary.upgraded == []
    assert UPDATES_NOTIFICATION in harness.hass.ids()


async def test_auto_update_installs(harness: Harness, source: Path) -> None:
    repo = await harness.repos.add(source.as_uri(), auto_update=True)
    await harness.repos.install(repo.id)
    _release(source, "1.1.0")

    summary = await harness.updater.run_once()

    assert summary.upgraded == [repo.slug]
    assert summary.updates == []
    installed = harness.targets.ha_config_dir / "custom_components" / "demo" / "sensor.py"
    assert installed.read_text(encoding="utf-8") == "VERSION = '1.1.0'"
    assert "psm_auto_updated" in harness.hass.ids()


async def test_no_notification_when_disabled(
    harness: Harness, source: Path, tmp_path: Path
) -> None:
    settings = make_settings(tmp_path)
    quiet = Updater(
        harness.repos,
        harness.credentials,
        harness.vault,
        harness.hass,
        type(settings)(**{**settings.__dict__, "notify_on_update": False}),
    )
    repo = await harness.repos.add(source.as_uri())
    await harness.repos.install(repo.id)
    _release(source, "1.1.0")

    await quiet.run_once()

    assert UPDATES_NOTIFICATION not in harness.hass.ids()


async def test_locked_repositories_are_skipped_and_reported_once(
    harness: Harness, source: Path
) -> None:
    await harness.vault.set_passphrase(PASSPHRASE)
    credential = harness.credentials.create_token("tok", Tier.PROTECTED, "secret-value")
    repo = await harness.repos.add(source.as_uri(), credential_id=credential.id)
    await harness.repos.install(repo.id)

    harness.vault.lock()

    first = await harness.updater.run_once()
    assert first.checked == 0
    assert first.skipped_locked == 1
    assert harness.hass.ids().count(LOCKED_NOTIFICATION) == 1

    second = await harness.updater.run_once()
    assert second.skipped_locked == 1
    # Still one notification, not one per sweep.
    assert harness.hass.ids().count(LOCKED_NOTIFICATION) == 1

    await harness.vault.unlock(PASSPHRASE)
    third = await harness.updater.run_once()
    assert third.skipped_locked == 0
    assert third.checked == 1
    assert LOCKED_NOTIFICATION in harness.hass.dismissed


async def test_unattended_repositories_are_checked_while_locked(
    harness: Harness, source: Path
) -> None:
    await harness.vault.set_passphrase(PASSPHRASE)
    credential = harness.credentials.create_token("tok", Tier.UNATTENDED, "secret-value")
    repo = await harness.repos.add(source.as_uri(), credential_id=credential.id)
    await harness.repos.install(repo.id)

    harness.vault.lock()
    summary = await harness.updater.run_once()

    assert summary.skipped_locked == 0
    assert summary.checked == 1


async def test_a_broken_repository_does_not_stop_the_sweep(
    harness: Harness, source: Path, tmp_path: Path
) -> None:
    good = await harness.repos.add(source.as_uri())
    await harness.repos.install(good.id)

    broken_source = tmp_path / "broken"
    (broken_source / "custom_components" / "demo").mkdir(parents=True)
    (broken_source / "custom_components" / "demo" / "manifest.json").write_text(
        '{"domain": "demo"}', encoding="utf-8"
    )
    _git(broken_source, "init", "-q", "-b", "main")
    _git(broken_source, "add", "-A")
    _git(broken_source, "commit", "-q", "-m", "initial")
    _git(broken_source, "tag", "v1.0.0")
    broken = await harness.repos.add(broken_source.as_uri())

    # Move the remote out from under it. Renaming rather than deleting because git
    # marks its object files read only, which defeats rmtree on Windows.
    broken_source.rename(tmp_path / "moved-away")
    _release(source, "1.1.0")

    summary = await harness.updater.run_once()

    assert broken.slug in summary.failed
    assert summary.checked == 1
    assert summary.updates == [f"{good.slug} v1.1.0"]
