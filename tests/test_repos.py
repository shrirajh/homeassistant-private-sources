"""Repository records and the full add, install, upgrade, remove flow."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from psm.content import Category, Targets
from psm.credentials import CredentialStore
from psm.db import Database
from psm.gitops import Git, Ref
from psm.hass import HomeAssistant
from psm.installer import Installer
from psm.keystore import LocalKeystore
from psm.repos import (
    RepositoryError,
    RepositoryStore,
    UnknownRepository,
    latest_tag,
    parse_url,
    version_key,
)
from psm.vault import Tier, Vault

_GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.invalid",
}


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, env=_GIT_ENV)


@pytest.fixture
def targets(tmp_path: Path) -> Targets:
    return Targets(ha_config_dir=tmp_path / "homeassistant", addons_dir=tmp_path / "addons")


@pytest.fixture
def store(tmp_path: Path, targets: Targets) -> RepositoryStore:
    keystore_dir = tmp_path / "keystore"
    keystore_dir.mkdir()
    db = Database(tmp_path / "psm.db")
    vault = Vault(db, LocalKeystore(keystore_dir))
    vault.start()
    return RepositoryStore(
        db,
        CredentialStore(db, vault),
        Git(tmp_path / "cache", tmp_path / "known_hosts"),
        Installer(db, targets),
        HomeAssistant(None),
        targets,
    )


@pytest.fixture
def integration_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "source"
    demo = repo / "custom_components" / "demo"
    demo.mkdir(parents=True)
    (demo / "manifest.json").write_text('{"domain": "demo", "version": "1.0.0"}', encoding="utf-8")
    (demo / "sensor.py").write_text("VERSION = '1.0.0'", encoding="utf-8")
    (repo / "hacs.json").write_text('{"name": "Demo Integration"}', encoding="utf-8")
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "initial")
    _git(repo, "tag", "v1.0.0")
    return repo


def _release(repo: Path, version: str) -> None:
    target = repo / "custom_components" / "demo" / "sensor.py"
    target.write_text(f"VERSION = '{version}'", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", version)
    _git(repo, "tag", f"v{version}")


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://github.com/owner/repo", ("github.com", "owner", "repo")),
        ("https://github.com/owner/repo.git", ("github.com", "owner", "repo")),
        ("https://github.com/owner/repo/", ("github.com", "owner", "repo")),
        ("git@github.com:owner/repo.git", ("github.com", "owner", "repo")),
        ("ssh://git@gitlab.com/group/sub/repo.git", ("gitlab.com", "group/sub", "repo")),
        ("git@gitlab.example.org:group/sub/repo.git", ("gitlab.example.org", "group/sub", "repo")),
        ("https://gitea.lan:3000/me/thing.git", ("gitea.lan", "me", "thing")),
    ],
)
def test_parse_url(url: str, expected: tuple[str, str, str]) -> None:
    assert parse_url(url) == expected


@pytest.mark.parametrize("url", ["", "nonsense", "https://github.com/onlyowner"])
def test_parse_url_rejects_junk(url: str) -> None:
    with pytest.raises(RepositoryError):
        parse_url(url)


def test_version_ordering() -> None:
    tags = ["v1.0.0", "v1.10.0", "v1.2.0", "v0.9.9"]
    assert max(tags, key=version_key) == "v1.10.0"


def test_latest_tag_prefers_stable() -> None:
    refs = [
        Ref("v1.0.0", "tag", "a" * 40),
        Ref("v2.0.0-rc1", "tag", "b" * 40),
        Ref("main", "branch", "c" * 40),
    ]
    assert latest_tag(refs) == "v1.0.0"
    assert latest_tag(refs, allow_prerelease=True) == "v2.0.0-rc1"


def test_latest_tag_without_tags() -> None:
    assert latest_tag([Ref("main", "branch", "a" * 40)]) is None


async def test_add_detects_category_and_reads_hacs_json(
    store: RepositoryStore, integration_repo: Path
) -> None:
    repo = await store.add(integration_repo.as_uri())

    assert repo.category == Category.INTEGRATION.value
    assert repo.name == "source"
    assert repo.available_version == "v1.0.0"
    assert repo.installed is False


async def test_add_rejects_duplicates(store: RepositoryStore, integration_repo: Path) -> None:
    await store.add(integration_repo.as_uri())
    with pytest.raises(RepositoryError, match="already tracked"):
        await store.add(integration_repo.as_uri())


async def test_install_upgrade_and_remove(
    store: RepositoryStore, integration_repo: Path, targets: Targets
) -> None:
    repo = await store.add(integration_repo.as_uri())

    result = await store.install(repo.id)
    installed = targets.ha_config_dir / "custom_components" / "demo"
    assert result.files == 2
    assert (installed / "sensor.py").read_text(encoding="utf-8") == "VERSION = '1.0.0'"

    after = store.get(repo.id)
    assert after.installed is True
    assert after.installed_version == "v1.0.0"
    assert after.update_available is False

    _release(integration_repo, "1.1.0")
    refreshed = await store.refresh(repo.id)
    assert refreshed.available_version == "v1.1.0"
    assert refreshed.update_available is True

    await store.install(repo.id)
    assert (installed / "sensor.py").read_text(encoding="utf-8") == "VERSION = '1.1.0'"
    assert store.get(repo.id).update_available is False

    removal = await store.uninstall(repo.id)
    assert removal.clean
    assert not installed.exists()
    assert store.get(repo.id).installed is False


async def test_install_a_specific_ref(
    store: RepositoryStore, integration_repo: Path, targets: Targets
) -> None:
    _release(integration_repo, "2.0.0")
    repo = await store.add(integration_repo.as_uri())

    await store.install(repo.id, ref="v1.0.0")

    installed = targets.ha_config_dir / "custom_components" / "demo"
    assert (installed / "sensor.py").read_text(encoding="utf-8") == "VERSION = '1.0.0'"
    assert store.get(repo.id).installed_version == "v1.0.0"


async def test_branch_tracking(
    store: RepositoryStore, integration_repo: Path, targets: Targets
) -> None:
    repo = await store.add(integration_repo.as_uri(), ref_kind="branch")

    await store.install(repo.id)

    version = store.get(repo.id).installed_version
    assert version is not None
    assert version.startswith("main@")


async def test_rolling_branch_reports_updates_as_the_branch_moves(
    store: RepositoryStore, integration_repo: Path, targets: Targets
) -> None:
    """A branch that moves must register as an update, which is the point of rolling."""
    repo = await store.add(integration_repo.as_uri(), ref_kind="branch")
    await store.install(repo.id)

    installed = store.get(repo.id)
    assert installed.installed_version.startswith("main@")
    assert installed.update_available is False

    # A new commit on the branch, with no tag anywhere.
    (integration_repo / "custom_components" / "demo" / "sensor.py").write_text(
        "VERSION = 'rolling'", encoding="utf-8"
    )
    _git(integration_repo, "add", "-A")
    _git(integration_repo, "commit", "-q", "-m", "move the branch")

    refreshed = await store.refresh(repo.id)
    assert refreshed.update_available is True
    assert refreshed.available_version != installed.installed_version
    assert refreshed.available_version.startswith("main@")

    await store.install(repo.id)
    assert store.get(repo.id).update_available is False
    target = targets.ha_config_dir / "custom_components" / "demo" / "sensor.py"
    assert target.read_text(encoding="utf-8") == "VERSION = 'rolling'"


async def test_switching_to_rolling_recomputes_the_available_version(
    store: RepositoryStore, integration_repo: Path
) -> None:
    repo = await store.add(integration_repo.as_uri())
    await store.install(repo.id)
    assert store.get(repo.id).available_version == "v1.0.0"

    store.update_settings(repo.id, ref_kind="branch", clear_pin=True)
    await store.refresh_available(repo.id)

    assert store.get(repo.id).available_version.startswith("main@")


async def test_clearing_the_credential_stores_null_not_empty_string(
    store: RepositoryStore, integration_repo: Path
) -> None:
    """An empty string would violate the foreign key onto credentials."""
    credential = store._credentials.create_token("tok", Tier.UNATTENDED, "secret-value")
    repo = await store.add(integration_repo.as_uri(), credential_id=credential.id)
    assert store.get(repo.id).credential_id == credential.id

    store.update_settings(repo.id, credential_id="")

    assert store.get(repo.id).credential_id is None
    row = store._db.one("SELECT credential_id FROM repos WHERE id = ?", (repo.id,))
    assert row["credential_id"] is None
    # The credential is now unreferenced, so it must be deletable.
    store._credentials.delete(credential.id)


async def test_settings_left_unspecified_are_preserved(
    store: RepositoryStore, integration_repo: Path
) -> None:
    repo = await store.add(integration_repo.as_uri())
    store.update_settings(repo.id, pinned_ref="v1.0.0")

    store.update_settings(repo.id, auto_update=True)

    kept = store.get(repo.id)
    assert kept.pinned_ref == "v1.0.0"
    assert kept.auto_update is True


async def test_delete_removes_files_and_record(
    store: RepositoryStore, integration_repo: Path, targets: Targets
) -> None:
    repo = await store.add(integration_repo.as_uri())
    await store.install(repo.id)

    result = await store.delete(repo.id)

    assert result.clean
    assert not (targets.ha_config_dir / "custom_components" / "demo").exists()
    with pytest.raises(UnknownRepository):
        store.get(repo.id)


async def test_delete_refuses_when_files_were_edited(
    store: RepositoryStore, integration_repo: Path, targets: Targets
) -> None:
    repo = await store.add(integration_repo.as_uri())
    await store.install(repo.id)
    (targets.ha_config_dir / "custom_components" / "demo" / "sensor.py").write_text(
        "patched by hand", encoding="utf-8"
    )

    result = await store.delete(repo.id)

    assert not result.clean
    assert store.get(repo.id) is not None

    forced = await store.delete(repo.id, force=True)
    assert forced.clean


async def test_update_settings(store: RepositoryStore, integration_repo: Path) -> None:
    repo = await store.add(integration_repo.as_uri())

    changed = store.update_settings(repo.id, auto_update=True, ref_kind="branch")
    assert changed.auto_update is True
    assert changed.ref_kind == "branch"

    pinned = store.update_settings(repo.id, pinned_ref="v1.0.0")
    assert pinned.pinned_ref == "v1.0.0"

    assert store.update_settings(repo.id, clear_pin=True).pinned_ref is None


async def test_minimum_core_version_is_enforced(
    store: RepositoryStore, integration_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (integration_repo / "hacs.json").write_text(
        '{"name": "Demo", "homeassistant": "2099.1.0"}', encoding="utf-8"
    )
    _git(integration_repo, "add", "-A")
    _git(integration_repo, "commit", "-q", "-m", "require newer core")
    _git(integration_repo, "tag", "v1.2.0")

    repo = await store.add(integration_repo.as_uri())
    monkeypatch.setattr(HomeAssistant, "available", property(lambda self: True))
    monkeypatch.setattr(HomeAssistant, "core_version", _fake_version("2024.6.0"))

    with pytest.raises(RepositoryError, match="2099.1.0"):
        await store.install(repo.id)


def _fake_version(value: str):
    async def _core_version(self) -> str:
        return value

    return _core_version


async def test_unknown_repository(store: RepositoryStore) -> None:
    with pytest.raises(UnknownRepository):
        store.get("missing")
