"""HACS compatible content detection and install planning.

Mirrors the layout rules HACS uses so the same repositories work here, including
hacs.json handling for content_in_root, filename and persistent_directory.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

_LOGGER = logging.getLogger(__name__)


class Category(StrEnum):
    INTEGRATION = "integration"
    PLUGIN = "plugin"
    THEME = "theme"
    PYTHON_SCRIPT = "python_script"
    APPDAEMON = "appdaemon"
    ADDON = "addon"


class ContentError(Exception):
    """The repository does not contain what the chosen category needs."""


@dataclass(frozen=True)
class HacsManifest:
    name: str | None = None
    content_in_root: bool = False
    filename: str | None = None
    hide_default_branch: bool = False
    zip_release: bool = False
    homeassistant: str | None = None
    persistent_directory: str | None = None
    country: list[str] = field(default_factory=list)

    @classmethod
    def parse(cls, raw: bytes | str | None) -> HacsManifest:
        if not raw:
            return cls()
        try:
            data = json.loads(raw)
        except ValueError:
            _LOGGER.warning("Ignoring malformed hacs.json")
            return cls()
        if not isinstance(data, dict):
            return cls()

        country = data.get("country")
        if isinstance(country, str):
            country = [country]
        elif not isinstance(country, list):
            country = []

        return cls(
            name=data.get("name"),
            content_in_root=bool(data.get("content_in_root", False)),
            filename=data.get("filename"),
            hide_default_branch=bool(data.get("hide_default_branch", False)),
            zip_release=bool(data.get("zip_release", False)),
            homeassistant=data.get("homeassistant"),
            persistent_directory=data.get("persistent_directory"),
            country=[str(c) for c in country],
        )


@dataclass(frozen=True)
class Targets:
    ha_config_dir: Path
    addons_dir: Path


@dataclass(frozen=True)
class Plan:
    category: Category
    files: list[tuple[Path, Path]]
    swap_root: Path | None = None
    resource_url: str | None = None
    addon_slug: str | None = None
    domain: str | None = None
    persistent_directory: str | None = None

    @property
    def destinations(self) -> list[Path]:
        return [dest for _, dest in self.files]


def detect(files: Sequence[str], manifest: HacsManifest | None = None) -> Category | None:
    """Best guess at what a repository contains, using the same signals as HACS."""
    manifest = manifest or HacsManifest()
    names = set(files)
    roots = {path.split("/")[0] for path in files if "/" in path}

    if "repository.yaml" in names or "repository.json" in names:
        return Category.ADDON
    if ("config.yaml" in names or "config.json" in names) and "Dockerfile" in names:
        return Category.ADDON

    if any(p.startswith("custom_components/") and p.endswith("/manifest.json") for p in files):
        return Category.INTEGRATION
    if manifest.content_in_root and "manifest.json" in names:
        return Category.INTEGRATION

    if "appdaemon" in roots or any(p.startswith("apps/") and p.endswith(".py") for p in files):
        return Category.APPDAEMON
    if any(p.startswith("python_scripts/") and p.endswith(".py") for p in files):
        return Category.PYTHON_SCRIPT
    if any(p.startswith("themes/") and p.endswith((".yaml", ".yml")) for p in files):
        return Category.THEME

    if any(p.startswith("dist/") and p.endswith(".js") for p in files):
        return Category.PLUGIN
    if any("/" not in p and p.endswith(".js") for p in files):
        return Category.PLUGIN

    return None


def _walk(root: Path) -> Iterator[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_file():
            yield path


def _candidate_js_names(repo_name: str) -> list[str]:
    names = [f"{repo_name}.js"]
    if repo_name.startswith("lovelace-"):
        names.append(f"{repo_name.removeprefix('lovelace-')}.js")
    return names


def _integration(staging: Path, manifest: HacsManifest, targets: Targets) -> Plan:
    components = targets.ha_config_dir / "custom_components"

    if manifest.content_in_root:
        domain = _domain_from_manifest(staging / "manifest.json")
        root = components / domain
        return Plan(
            Category.INTEGRATION,
            [(p, root / p.relative_to(staging)) for p in _walk(staging)],
            swap_root=root,
            domain=domain,
            persistent_directory=manifest.persistent_directory,
        )

    base = staging / "custom_components"
    domains = [p for p in sorted(base.iterdir()) if p.is_dir()] if base.is_dir() else []
    if not domains:
        raise ContentError("no custom_components/<domain> directory found")
    if len(domains) > 1:
        _LOGGER.warning("Repository ships %d integrations, installing all of them", len(domains))

    files: list[tuple[Path, Path]] = []
    for directory in domains:
        root = components / directory.name
        files += [(p, root / p.relative_to(directory)) for p in _walk(directory)]

    return Plan(
        Category.INTEGRATION,
        files,
        # Only a single domain can be swapped atomically as one directory.
        swap_root=components / domains[0].name if len(domains) == 1 else None,
        domain=domains[0].name,
        persistent_directory=manifest.persistent_directory,
    )


def _domain_from_manifest(path: Path) -> str:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        raise ContentError("manifest.json is missing or malformed") from err
    domain = data.get("domain")
    if not domain:
        raise ContentError("manifest.json has no domain")
    return str(domain)


def _plugin(staging: Path, repo_name: str, manifest: HacsManifest, targets: Targets) -> Plan:
    root = targets.ha_config_dir / "www" / "community" / repo_name
    dist = staging / "dist"

    if dist.is_dir():
        files = [(p, root / p.relative_to(dist)) for p in _walk(dist)]
        top_level = [dest.name for _, dest in files if dest.parent == root]
        entry = _entry_point(top_level, repo_name, manifest)
    else:
        wanted = [manifest.filename] if manifest.filename else _candidate_js_names(repo_name)
        found = next((staging / n for n in wanted if (staging / n).is_file()), None)
        if found is None:
            loose = [p for p in staging.glob("*.js") if p.is_file()]
            if len(loose) != 1:
                raise ContentError(
                    f"could not find a javascript entry point, tried {', '.join(wanted)}"
                )
            found = loose[0]
        files = [(found, root / found.name)]
        extra = found.with_suffix(".js.map")
        if extra.is_file():
            files.append((extra, root / extra.name))
        entry = found.name

    return Plan(
        Category.PLUGIN,
        files,
        swap_root=root,
        resource_url=f"/local/community/{repo_name}/{entry}",
    )


def _entry_point(names: Sequence[str], repo_name: str, manifest: HacsManifest) -> str:
    if manifest.filename and manifest.filename in names:
        return manifest.filename
    for candidate in _candidate_js_names(repo_name):
        if candidate in names:
            return candidate
    scripts = [n for n in names if n.endswith(".js")]
    if not scripts:
        raise ContentError("no javascript file to register as a Lovelace resource")
    return scripts[0]


def _flat(
    staging: Path,
    category: Category,
    source_dir: str,
    suffixes: tuple[str, ...],
    dest_dir: Path,
    manifest: HacsManifest,
) -> Plan:
    base = staging if manifest.content_in_root else staging / source_dir
    if not base.is_dir():
        raise ContentError(f"no {source_dir}/ directory found")

    files = [(p, dest_dir / p.relative_to(base)) for p in _walk(base) if p.name.endswith(suffixes)]
    if not files:
        raise ContentError(f"no {' or '.join(suffixes)} files under {source_dir}/")
    return Plan(category, files)


def _appdaemon(staging: Path, repo_name: str, manifest: HacsManifest, targets: Targets) -> Plan:
    base = staging if manifest.content_in_root else staging / "apps"
    if not base.is_dir():
        raise ContentError("no apps/ directory found")

    inner = [p for p in sorted(base.iterdir()) if p.is_dir()]
    source = inner[0] if len(inner) == 1 else base
    name = source.name if len(inner) == 1 else repo_name

    root = targets.ha_config_dir / "appdaemon" / "apps" / name
    return Plan(
        Category.APPDAEMON,
        [(p, root / p.relative_to(source)) for p in _walk(source)],
        swap_root=root,
    )


def _addon(staging: Path, repo_name: str, targets: Targets) -> Plan:
    root = targets.addons_dir / repo_name
    files = [(p, root / p.relative_to(staging)) for p in _walk(staging)]
    if not files:
        raise ContentError("repository is empty")
    return Plan(Category.ADDON, files, swap_root=root, addon_slug=repo_name)


def plan(
    category: Category,
    staging: Path,
    repo_name: str,
    manifest: HacsManifest,
    targets: Targets,
) -> Plan:
    if category is Category.INTEGRATION:
        return _integration(staging, manifest, targets)
    if category is Category.PLUGIN:
        return _plugin(staging, repo_name, manifest, targets)
    if category is Category.THEME:
        return _flat(
            staging,
            category,
            "themes",
            (".yaml", ".yml"),
            targets.ha_config_dir / "themes",
            manifest,
        )
    if category is Category.PYTHON_SCRIPT:
        return _flat(
            staging,
            category,
            "python_scripts",
            (".py",),
            targets.ha_config_dir / "python_scripts",
            manifest,
        )
    if category is Category.APPDAEMON:
        return _appdaemon(staging, repo_name, manifest, targets)
    if category is Category.ADDON:
        return _addon(staging, repo_name, targets)
    raise ContentError(f"unsupported category {category}")
