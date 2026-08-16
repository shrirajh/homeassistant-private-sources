"""Validate the add-on manifest.

home-assistant/actions/hassio-addon-lint no longer exists, and swapping in another
third party action just moves the same problem. These checks are the ones that
actually catch mistakes here, and they cost nothing to run.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ADDON = ROOT / "private_source_manager"

KNOWN_ARCH = {"aarch64", "amd64", "armhf", "armv7", "i386"}
REQUIRED = ("name", "version", "slug", "description", "arch")

problems: list[str] = []


def fail(message: str) -> None:
    problems.append(message)


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as err:
        fail(f"{path.relative_to(ROOT)}: {err}")
        return {}
    if not isinstance(data, dict):
        fail(f"{path.relative_to(ROOT)}: expected a mapping")
        return {}
    return data


def check_config(config: dict[str, Any], build: dict[str, Any]) -> None:
    for key in REQUIRED:
        if key not in config:
            fail(f"config.yaml: missing required key {key}")

    if config.get("slug") != ADDON.name:
        fail(f"config.yaml: slug {config.get('slug')!r} does not match directory {ADDON.name!r}")

    if not isinstance(config.get("version"), str):
        fail("config.yaml: version must be quoted so 1.10 is not read as a float")

    arches = config.get("arch") or []
    if not arches:
        fail("config.yaml: arch must list at least one architecture")
    for arch in arches:
        if arch not in KNOWN_ARCH:
            fail(f"config.yaml: unknown architecture {arch}")

    build_from = build.get("build_from") or {}
    for arch in arches:
        if arch not in build_from:
            fail(f"build.yaml: no build_from entry for {arch}, which config.yaml declares")
    for arch in build_from:
        if arch not in arches:
            fail(f"build.yaml: build_from has {arch}, which config.yaml does not declare")

    if config.get("ingress") and not config.get("ingress_port"):
        fail("config.yaml: ingress is enabled but ingress_port is not set")


def check_options(config: dict[str, Any]) -> None:
    options = config.get("options") or {}
    schema = config.get("schema") or {}
    for key in options:
        if key not in schema:
            fail(f"config.yaml: option {key} has no schema entry")
    for key in schema:
        if key not in options and not str(schema[key]).endswith("?"):
            fail(f"config.yaml: schema {key} is required but has no default in options")


def check_changelog(config: dict[str, Any]) -> None:
    path = ADDON / "CHANGELOG.md"
    if not path.is_file():
        fail("CHANGELOG.md is missing")
        return
    headings = re.findall(r"^##\s+(.+?)\s*$", path.read_text(encoding="utf-8"), re.MULTILINE)
    if not headings:
        fail("CHANGELOG.md has no version heading")
        return
    version = config.get("version")
    if headings[0] != version:
        fail(f"CHANGELOG.md top entry {headings[0]!r} does not match version {version!r}")


def check_files() -> None:
    for name in ("Dockerfile", "README.md", "DOCS.md", "requirements.txt", "apparmor.txt"):
        if not (ADDON / name).is_file():
            fail(f"{name} is missing")

    run = ADDON / "rootfs/etc/s6-overlay/s6-rc.d/psm/run"
    if not run.is_file():
        fail("the s6 run script is missing")
    elif b"\r\n" in run.read_bytes():
        fail("the s6 run script has CRLF line endings and will not execute in the container")

    index = ADDON / "app/psm/static/index.html"
    if not index.is_file():
        fail("the frontend bundle is missing, run npm run build in frontend/")
    elif '<base href="/">' not in index.read_text(encoding="utf-8"):
        fail("static/index.html lost its literal base href, ingress rewriting will break")


def check_images() -> None:
    icon = ADDON / "icon.png"
    logo = ADDON / "logo.png"
    if not icon.is_file():
        fail("icon.png is missing")
    else:
        width, height = Image.open(icon).size
        if width != height:
            fail(f"icon.png must be square, got {width}x{height}")
    if not logo.is_file():
        fail("logo.png is missing")


def check_repository() -> None:
    repository = load_yaml(ROOT / "repository.yaml")
    for key in ("name", "url", "maintainer"):
        if key not in repository:
            fail(f"repository.yaml: missing {key}")

    # A private address here would be published the moment the repo goes public.
    maintainer = str(repository.get("maintainer", ""))
    match = re.search(r"<([^>]+)>", maintainer)
    if match and not match.group(1).endswith("users.noreply.github.com"):
        fail(f"repository.yaml: maintainer uses {match.group(1)}, prefer a noreply address")


def check_requirements() -> None:
    path = ADDON / "requirements.txt"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        entry = line.strip()
        if entry and not entry.startswith("#") and "==" not in entry:
            fail(f"requirements.txt: {entry} is not pinned")


def main() -> int:
    config = load_yaml(ADDON / "config.yaml")
    build = load_yaml(ADDON / "build.yaml")

    if config:
        check_config(config, build)
        check_options(config)
        check_changelog(config)
    check_files()
    check_images()
    check_repository()
    check_requirements()

    if problems:
        print(f"{len(problems)} problem(s):", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print(f"add-on manifest is valid: {config.get('name')} {config.get('version')}")
    print(f"  architectures: {', '.join(config.get('arch', []))}")
    print(f"  options: {', '.join(config.get('options', {}))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
