"""Transactional install, upgrade and removal."""

from __future__ import annotations

from pathlib import Path

import pytest

from psm.content import Category, HacsManifest, Plan, Targets
from psm.content import plan as make_plan
from psm.db import Database
from psm.installer import Installer, sha256_file


@pytest.fixture
def targets(tmp_path: Path) -> Targets:
    return Targets(ha_config_dir=tmp_path / "homeassistant", addons_dir=tmp_path / "addons")


@pytest.fixture
def db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "psm.db")
    # installed_files has a foreign key onto repos, so the owning row must exist.
    database.execute(
        """INSERT INTO repos (id, url, host, owner, name, category)
           VALUES ('repo1', 'https://example.invalid/a/b', 'example.invalid', 'a', 'b',
                   'integration')"""
    )
    return database


@pytest.fixture
def installer(db: Database, targets: Targets) -> Installer:
    return Installer(db, targets)


def _staging(root: Path, files: dict[str, str]) -> Path:
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


def _integration(tmp_path: Path, targets: Targets, version: str, extra: dict | None = None) -> Plan:
    files = {
        "custom_components/demo/manifest.json": f'{{"domain": "demo", "version": "{version}"}}',
        "custom_components/demo/sensor.py": f"VERSION = '{version}'",
    }
    files.update(extra or {})
    staging = _staging(tmp_path / f"staging-{version}", files)
    return make_plan(Category.INTEGRATION, staging, "demo", HacsManifest(), targets)


def test_install_writes_files_and_records_hashes(
    installer: Installer, targets: Targets, tmp_path: Path
) -> None:
    result = installer.apply("repo1", _integration(tmp_path, targets, "1.0.0"))

    installed = targets.ha_config_dir / "custom_components" / "demo"
    assert result.files == 2
    assert result.domain == "demo"
    assert (installed / "manifest.json").is_file()
    assert (installed / "sensor.py").read_text(encoding="utf-8") == "VERSION = '1.0.0'"
    assert sorted(Path(p).name for p in installer.tracked("repo1")) == [
        "manifest.json",
        "sensor.py",
    ]


def test_upgrade_removes_files_dropped_upstream(
    installer: Installer, targets: Targets, tmp_path: Path
) -> None:
    installer.apply(
        "repo1",
        _integration(tmp_path, targets, "1.0.0", {"custom_components/demo/legacy.py": "old"}),
    )
    installed = targets.ha_config_dir / "custom_components" / "demo"
    assert (installed / "legacy.py").is_file()

    installer.apply("repo1", _integration(tmp_path, targets, "2.0.0"))

    assert not (installed / "legacy.py").exists()
    assert (installed / "sensor.py").read_text(encoding="utf-8") == "VERSION = '2.0.0'"


def test_persistent_directory_survives_upgrade(
    installer: Installer, targets: Targets, tmp_path: Path
) -> None:
    manifest = HacsManifest(persistent_directory="data")
    first = _staging(
        tmp_path / "s1",
        {
            "custom_components/demo/manifest.json": '{"domain": "demo"}',
            "custom_components/demo/data/keep.txt": "user data",
        },
    )
    installer.apply("repo1", make_plan(Category.INTEGRATION, first, "demo", manifest, targets))

    installed = targets.ha_config_dir / "custom_components" / "demo"
    (installed / "data" / "keep.txt").write_text("edited by user", encoding="utf-8")

    second = _staging(
        tmp_path / "s2", {"custom_components/demo/manifest.json": '{"domain":"demo"}'}
    )
    installer.apply("repo1", make_plan(Category.INTEGRATION, second, "demo", manifest, targets))

    assert (installed / "data" / "keep.txt").read_text(encoding="utf-8") == "edited by user"


def test_remove_deletes_tracked_files_and_prunes(
    installer: Installer, targets: Targets, tmp_path: Path
) -> None:
    installer.apply("repo1", _integration(tmp_path, targets, "1.0.0"))
    installed = targets.ha_config_dir / "custom_components" / "demo"

    result = installer.remove("repo1")

    assert result.removed == 2
    assert result.clean
    assert not installed.exists()
    # The shared parent must survive.
    assert (targets.ha_config_dir / "custom_components").is_dir()
    assert installer.tracked("repo1") == []


def test_remove_reports_locally_modified_files(
    installer: Installer, targets: Targets, tmp_path: Path
) -> None:
    installer.apply("repo1", _integration(tmp_path, targets, "1.0.0"))
    installed = targets.ha_config_dir / "custom_components" / "demo"
    (installed / "sensor.py").write_text("locally patched", encoding="utf-8")

    result = installer.remove("repo1")

    assert not result.clean
    assert result.modified == [str(installed / "sensor.py")]
    assert (installed / "sensor.py").is_file()
    assert not (installed / "manifest.json").exists()
    # Manifest is retained so the modified file stays tracked.
    assert installer.tracked("repo1")


def test_force_remove_deletes_modified_files(
    installer: Installer, targets: Targets, tmp_path: Path
) -> None:
    installer.apply("repo1", _integration(tmp_path, targets, "1.0.0"))
    installed = targets.ha_config_dir / "custom_components" / "demo"
    (installed / "sensor.py").write_text("locally patched", encoding="utf-8")

    result = installer.remove("repo1", force=True)

    assert result.clean
    assert result.removed == 2
    assert not installed.exists()


def test_remove_counts_missing_files(
    installer: Installer, targets: Targets, tmp_path: Path
) -> None:
    installer.apply("repo1", _integration(tmp_path, targets, "1.0.0"))
    (targets.ha_config_dir / "custom_components" / "demo" / "sensor.py").unlink()

    result = installer.remove("repo1")

    assert result.missing == 1
    assert result.removed == 1


def test_loose_files_do_not_prune_shared_directory(
    installer: Installer, targets: Targets, tmp_path: Path
) -> None:
    staging = _staging(tmp_path / "themes", {"themes/dark.yaml": "dark:"})
    installer.apply(
        "repo1", make_plan(Category.THEME, staging, "themes-repo", HacsManifest(), targets)
    )
    other = targets.ha_config_dir / "themes" / "handwritten.yaml"
    other.write_text("mine:", encoding="utf-8")

    installer.remove("repo1")

    assert other.is_file()
    assert not (targets.ha_config_dir / "themes" / "dark.yaml").exists()


def test_addon_install_targets_the_addons_directory(
    installer: Installer, targets: Targets, tmp_path: Path
) -> None:
    staging = _staging(tmp_path / "addon", {"config.yaml": "slug: demo", "Dockerfile": "FROM x"})

    result = installer.apply(
        "repo1", make_plan(Category.ADDON, staging, "my-addon", HacsManifest(), targets)
    )

    assert result.addon_slug == "my-addon"
    assert (targets.addons_dir / "my-addon" / "config.yaml").is_file()


def test_failed_swap_leaves_previous_install_intact(
    installer: Installer, targets: Targets, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installer.apply("repo1", _integration(tmp_path, targets, "1.0.0"))
    installed = targets.ha_config_dir / "custom_components" / "demo"
    original = (installed / "sensor.py").read_text(encoding="utf-8")

    def _explode(*args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("psm.installer.shutil.copy2", _explode)
    with pytest.raises(OSError, match="disk full"):
        installer.apply("repo1", _integration(tmp_path, targets, "2.0.0"))

    assert (installed / "sensor.py").read_text(encoding="utf-8") == original


def test_sha256_matches_recorded_manifest(
    installer: Installer, db: Database, targets: Targets, tmp_path: Path
) -> None:
    installer.apply("repo1", _integration(tmp_path, targets, "1.0.0"))

    for row in db.all("SELECT path, sha256 FROM installed_files WHERE repo_id = 'repo1'"):
        assert sha256_file(Path(row["path"])) == row["sha256"]
