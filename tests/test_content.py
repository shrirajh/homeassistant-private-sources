"""HACS compatible detection and install planning."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from psm.content import Category, ContentError, HacsManifest, Targets, detect, plan


@pytest.fixture
def targets(tmp_path: Path) -> Targets:
    return Targets(ha_config_dir=tmp_path / "homeassistant", addons_dir=tmp_path / "addons")


def _tree(root: Path, files: dict[str, str]) -> Path:
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


def test_manifest_defaults() -> None:
    manifest = HacsManifest.parse(None)
    assert manifest.name is None
    assert manifest.content_in_root is False
    assert manifest.country == []


def test_manifest_parsing() -> None:
    manifest = HacsManifest.parse(
        json.dumps(
            {
                "name": "Demo",
                "content_in_root": True,
                "filename": "demo.js",
                "zip_release": True,
                "hide_default_branch": True,
                "homeassistant": "2024.1.0",
                "persistent_directory": "data",
                "country": "NO",
            }
        )
    )
    assert manifest.name == "Demo"
    assert manifest.content_in_root is True
    assert manifest.filename == "demo.js"
    assert manifest.persistent_directory == "data"
    assert manifest.country == ["NO"]


def test_manifest_survives_garbage() -> None:
    assert HacsManifest.parse(b"{not json").name is None
    assert HacsManifest.parse(b"[]").name is None


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        (["custom_components/demo/manifest.json"], Category.INTEGRATION),
        (["dist/my-card.js", "README.md"], Category.PLUGIN),
        (["my-card.js"], Category.PLUGIN),
        (["themes/dark.yaml"], Category.THEME),
        (["python_scripts/thing.py"], Category.PYTHON_SCRIPT),
        (["apps/myapp/main.py"], Category.APPDAEMON),
        (["repository.yaml", "myaddon/config.yaml"], Category.ADDON),
        (["config.yaml", "Dockerfile", "run.sh"], Category.ADDON),
        (["README.md", "LICENSE"], None),
    ],
)
def test_detect(files: list[str], expected: Category | None) -> None:
    assert detect(files) == expected


def test_detect_prefers_addon_over_plugin() -> None:
    assert detect(["repository.yaml", "dist/thing.js"]) is Category.ADDON


def test_detect_content_in_root_integration() -> None:
    manifest = HacsManifest(content_in_root=True)
    assert detect(["manifest.json", "sensor.py"], manifest) is Category.INTEGRATION


def test_plan_integration(tmp_path: Path, targets: Targets) -> None:
    staging = _tree(
        tmp_path / "staging",
        {
            "custom_components/demo/manifest.json": '{"domain": "demo"}',
            "custom_components/demo/sensor.py": "x = 1",
            "README.md": "ignored",
        },
    )

    result = plan(Category.INTEGRATION, staging, "demo-repo", HacsManifest(), targets)

    assert result.domain == "demo"
    assert result.swap_root == targets.ha_config_dir / "custom_components" / "demo"
    assert sorted(d.name for d in result.destinations) == ["manifest.json", "sensor.py"]
    assert not any("README" in str(d) for d in result.destinations)


def test_plan_integration_content_in_root(tmp_path: Path, targets: Targets) -> None:
    staging = _tree(
        tmp_path / "staging",
        {"manifest.json": '{"domain": "rooted"}', "__init__.py": ""},
    )

    result = plan(
        Category.INTEGRATION, staging, "repo", HacsManifest(content_in_root=True), targets
    )

    assert result.domain == "rooted"
    assert result.swap_root == targets.ha_config_dir / "custom_components" / "rooted"


def test_plan_integration_without_manifest(tmp_path: Path, targets: Targets) -> None:
    staging = _tree(tmp_path / "staging", {"README.md": "nothing here"})
    with pytest.raises(ContentError, match="custom_components"):
        plan(Category.INTEGRATION, staging, "repo", HacsManifest(), targets)


def test_plan_plugin_from_dist(tmp_path: Path, targets: Targets) -> None:
    staging = _tree(
        tmp_path / "staging",
        {"dist/my-card.js": "//", "dist/extra.css": "", "src/ignored.ts": ""},
    )

    result = plan(Category.PLUGIN, staging, "my-card", HacsManifest(), targets)

    root = targets.ha_config_dir / "www" / "community" / "my-card"
    assert result.swap_root == root
    assert result.resource_url == "/local/community/my-card/my-card.js"
    assert sorted(d.name for d in result.destinations) == ["extra.css", "my-card.js"]


def test_plan_plugin_strips_lovelace_prefix(tmp_path: Path, targets: Targets) -> None:
    staging = _tree(tmp_path / "staging", {"dist/awesome-card.js": "//"})

    result = plan(Category.PLUGIN, staging, "lovelace-awesome-card", HacsManifest(), targets)

    assert result.resource_url == "/local/community/lovelace-awesome-card/awesome-card.js"


def test_plan_plugin_from_root(tmp_path: Path, targets: Targets) -> None:
    staging = _tree(tmp_path / "staging", {"my-card.js": "//", "my-card.js.map": "{}"})

    result = plan(Category.PLUGIN, staging, "my-card", HacsManifest(), targets)

    assert sorted(d.name for d in result.destinations) == ["my-card.js", "my-card.js.map"]


def test_plan_plugin_honours_filename(tmp_path: Path, targets: Targets) -> None:
    staging = _tree(tmp_path / "staging", {"dist/renamed.js": "//"})

    result = plan(
        Category.PLUGIN, staging, "some-repo", HacsManifest(filename="renamed.js"), targets
    )

    assert result.resource_url == "/local/community/some-repo/renamed.js"


def test_plan_plugin_without_javascript(tmp_path: Path, targets: Targets) -> None:
    staging = _tree(tmp_path / "staging", {"README.md": ""})
    with pytest.raises(ContentError):
        plan(Category.PLUGIN, staging, "repo", HacsManifest(), targets)


def test_plan_theme(tmp_path: Path, targets: Targets) -> None:
    staging = _tree(tmp_path / "staging", {"themes/dark.yaml": "dark:", "README.md": ""})

    result = plan(Category.THEME, staging, "repo", HacsManifest(), targets)

    assert result.swap_root is None
    assert result.destinations == [targets.ha_config_dir / "themes" / "dark.yaml"]


def test_plan_python_script(tmp_path: Path, targets: Targets) -> None:
    staging = _tree(tmp_path / "staging", {"python_scripts/hello.py": "pass"})

    result = plan(Category.PYTHON_SCRIPT, staging, "repo", HacsManifest(), targets)

    assert result.destinations == [targets.ha_config_dir / "python_scripts" / "hello.py"]


def test_plan_appdaemon(tmp_path: Path, targets: Targets) -> None:
    staging = _tree(tmp_path / "staging", {"apps/myapp/main.py": "pass"})

    result = plan(Category.APPDAEMON, staging, "repo", HacsManifest(), targets)

    root = targets.ha_config_dir / "appdaemon" / "apps" / "myapp"
    assert result.swap_root == root
    assert result.destinations == [root / "main.py"]


def test_plan_addon(tmp_path: Path, targets: Targets) -> None:
    staging = _tree(
        tmp_path / "staging",
        {"config.yaml": "slug: demo", "Dockerfile": "FROM x", "rootfs/run": "#!/bin/sh"},
    )

    result = plan(Category.ADDON, staging, "my-addon", targets=targets, manifest=HacsManifest())

    assert result.addon_slug == "my-addon"
    assert result.swap_root == targets.addons_dir / "my-addon"
    assert len(result.destinations) == 3
