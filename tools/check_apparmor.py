"""Check the AppArmor profile covers what the add-on actually needs.

Two permissions matter here and both shipped broken once:

    x   AppArmor matches the resolved path, so a rule naming a symlink grants
        nothing. /usr/bin/bashio resolves to /usr/lib/bashio/bashio.
    m   Loading a shared library is an executable mmap. Read alone is not enough,
        so the dynamic linker could not map libpython.

Two modes:

    check_apparmor.py                     check the profile against recorded targets
    check_apparmor.py --from-image TAG    re-derive the targets from a built image

Refresh with --from-image whenever the base image or dependencies change.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILE = ROOT / "private_source_manager" / "apparmor.txt"
TARGETS = Path(__file__).resolve().parent / "apparmor_targets.json"

# Entry points the add-on runs, as invoked. What each resolves to is what the
# kernel checks, and that resolved path is what gets recorded.
ENTRY_POINTS = (
    "/init",
    "/command/with-contenv",
    "/command/execlineb",
    "/usr/bin/bashio",
    "/usr/bin/env",
    "/bin/bash",
    "/bin/sh",
    "/usr/local/bin/python3",
    "/opt/psm/psm/bin/askpass.sh",
    "/usr/bin/git",
    "/usr/libexec/git-core/git-remote-https",
    "/usr/bin/ssh",
    "/usr/bin/ssh-keyscan",
)

_RULE = re.compile(r"^(/\S*)\s+([a-zA-Z]+)\s*,")

# Targets are derived from an amd64 image, but the add-on also ships aarch64.
# Checking the substituted path catches a rule that hard codes one architecture.
_ARCH_SWAP = ("x86_64", "aarch64")


def parse_rules(profile: str) -> list[tuple[str, str]]:
    rules: list[tuple[str, str]] = []
    for raw in profile.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "deny")):
            continue
        match = _RULE.match(line)
        if match:
            rules.append((match.group(1), match.group(2)))
    return rules


def glob_to_regex(glob: str) -> re.Pattern[str]:
    """Translate the AppArmor glob subset this profile uses into a regex."""
    out = ["^"]
    index = 0
    while index < len(glob):
        if glob.startswith("**", index):
            out.append(".*")
            index += 2
        elif glob[index] == "*":
            out.append("[^/]*")
            index += 1
        elif glob[index] == "{":
            close = glob.index("}", index)
            options = glob[index + 1 : close].split(",")
            body = "|".join(re.escape(o) for o in options).replace(r"\*", "[^/]*")
            out.append(f"(?:{body})")
            index = close + 1
        else:
            out.append(re.escape(glob[index]))
            index += 1
    out.append("$")
    return re.compile("".join(out))


def grants(path: str, rules: list[tuple[str, str]], mode: str) -> bool:
    return any(mode in modes and glob_to_regex(glob).match(path) for glob, modes in rules)


def _variants(path: str) -> list[str]:
    if _ARCH_SWAP[0] in path:
        return [path, path.replace(*_ARCH_SWAP)]
    return [path]


def _run(tag: str, script: str) -> str:
    result = subprocess.run(
        ["docker", "run", "--rm", "--entrypoint", "sh", tag, "-c", script],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def derive_from_image(tag: str) -> dict[str, object]:
    resolve = "; ".join(
        f'printf "%s\\t%s\\n" "{p}" "$(readlink -f {p} 2>/dev/null)"' for p in ENTRY_POINTS
    )
    execs: dict[str, str] = {}
    for line in _run(tag, resolve).splitlines():
        entry, _, target = line.partition("\t")
        if entry and target:
            execs[entry] = target

    # Every shared object the loader maps: interpreter, ldd dependencies of each
    # binary, and one representative compiled module per package directory.
    libraries = _run(
        tag,
        r"""
        ls /lib/ld-musl-*.so.1 2>/dev/null
        for b in """
        + " ".join(sorted(set(execs.values())))
        + r"""; do
            ldd "$b" 2>/dev/null | sed -n 's/.*=> \(\/[^ ]*\).*/\1/p'
        done
        for d in $(find /usr/local/lib/python3.*/lib-dynload \
                        /usr/local/lib/python3.*/site-packages \
                        -name '*.so' 2>/dev/null | sed 's|/[^/]*$||' | sort -u); do
            find "$d" -maxdepth 1 -name '*.so' 2>/dev/null | head -1
        done
        """,
    )
    unique = sorted(
        {line.strip() for line in libraries.splitlines() if line.strip().startswith("/")}
    )
    return {"exec": execs, "mmap": unique}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-image", metavar="TAG", help="re-derive targets from a built image")
    args = parser.parse_args()

    if args.from_image:
        derived = derive_from_image(args.from_image)
        TARGETS.write_text(json.dumps(derived, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(
            f"recorded {len(derived['exec'])} exec and {len(derived['mmap'])} mmap targets"
            f" in {TARGETS.relative_to(ROOT)}"
        )

    if not TARGETS.is_file():
        print(f"{TARGETS.relative_to(ROOT)} is missing, run --from-image first", file=sys.stderr)
        return 1

    targets = json.loads(TARGETS.read_text(encoding="utf-8"))
    rules = parse_rules(PROFILE.read_text(encoding="utf-8"))
    if not rules:
        print("the profile has no file rules at all", file=sys.stderr)
        return 1

    gaps: list[str] = []
    checked = 0

    for entry, target in sorted(targets["exec"].items()):
        for candidate in _variants(target):
            checked += 1
            if not grants(candidate, rules, "x"):
                via = "" if entry == candidate else f", reached via {entry}"
                gaps.append(f"execute denied on {candidate}{via}")

    for library in targets["mmap"]:
        for candidate in _variants(library):
            checked += 1
            if not grants(candidate, rules, "m"):
                gaps.append(f"mmap denied on {candidate}, the loader cannot map it")

    if gaps:
        print(f"{len(gaps)} gap(s) in the profile:", file=sys.stderr)
        for gap in gaps:
            print(f"  - {gap}", file=sys.stderr)
        print(
            "\nAppArmor matches resolved paths, and shared libraries need m as well as r.",
            file=sys.stderr,
        )
        return 1

    print(
        f"profile covers all {len(targets['exec'])} exec and {len(targets['mmap'])} mmap targets"
        f" ({checked} checks including the aarch64 substitution)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
