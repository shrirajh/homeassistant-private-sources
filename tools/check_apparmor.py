"""Check the AppArmor profile covers everything the add-on actually executes.

The kernel matches on the resolved path, so a rule for a symlink grants nothing.
That is exactly how the first version of this profile shipped broken: /usr/bin/bashio
is a symlink to /usr/lib/bashio/bashio, which the profile only allowed to be read.

Two modes:

    check_apparmor.py                     check the profile against the recorded targets
    check_apparmor.py --from-image TAG    re-derive the targets from a built image

Refresh with --from-image whenever the base image changes.
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
TARGETS = Path(__file__).resolve().parent / "apparmor_exec_targets.json"

# Entry points the add-on runs, as invoked. The resolved target of each is what the
# kernel actually checks, and what gets recorded in apparmor_exec_targets.json.
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


def parse_exec_rules(profile: str) -> list[str]:
    """Return the path globs the profile grants some form of execute on.

    Any mode containing x grants execute, covering ix, rix, Px, Cx and ux alike.
    """
    globs: list[str] = []
    for raw in profile.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "deny")):
            continue
        match = _RULE.match(line)
        if match and "x" in match.group(2):
            globs.append(match.group(1))
    return globs


def glob_to_regex(glob: str) -> re.Pattern[str]:
    """Translate the AppArmor glob subset this profile uses into a regex."""
    out = ["^"]
    index = 0
    while index < len(glob):
        char = glob[index]
        if glob.startswith("**", index):
            out.append(".*")
            index += 2
        elif char == "*":
            out.append("[^/]*")
            index += 1
        elif char == "{":
            close = glob.index("}", index)
            options = glob[index + 1 : close].split(",")
            out.append(
                "(?:" + "|".join(re.escape(o) for o in options).replace(r"\*", "[^/]*") + ")"
            )
            index = close + 1
        else:
            out.append(re.escape(char))
            index += 1
    out.append("$")
    return re.compile("".join(out))


def covered(path: str, globs: list[str]) -> str | None:
    for glob in globs:
        if glob_to_regex(glob).match(path):
            return glob
    return None


def derive_from_image(tag: str) -> dict[str, str]:
    script = "; ".join(
        f'printf "%s\\t%s\\n" "{p}" "$(readlink -f {p} 2>/dev/null)"' for p in ENTRY_POINTS
    )
    result = subprocess.run(
        ["docker", "run", "--rm", "--entrypoint", "sh", tag, "-c", script],
        capture_output=True,
        text=True,
        check=True,
    )
    resolved: dict[str, str] = {}
    for line in result.stdout.splitlines():
        entry, _, target = line.partition("\t")
        if entry and target:
            resolved[entry] = target
    missing = [p for p in ENTRY_POINTS if p not in resolved]
    if missing:
        print(f"warning: not present in the image: {', '.join(missing)}", file=sys.stderr)
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-image", metavar="TAG", help="re-derive targets from a built image")
    args = parser.parse_args()

    if args.from_image:
        resolved = derive_from_image(args.from_image)
        TARGETS.write_text(json.dumps(resolved, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"recorded {len(resolved)} exec targets in {TARGETS.relative_to(ROOT)}")

    if not TARGETS.is_file():
        print(f"{TARGETS.relative_to(ROOT)} is missing, run --from-image first", file=sys.stderr)
        return 1

    resolved = json.loads(TARGETS.read_text(encoding="utf-8"))
    globs = parse_exec_rules(PROFILE.read_text(encoding="utf-8"))
    if not globs:
        print("the profile grants no execute rules at all", file=sys.stderr)
        return 1

    gaps: list[tuple[str, str]] = []
    for entry, target in sorted(resolved.items()):
        rule = covered(target, globs)
        if rule is None:
            gaps.append((entry, target))
        else:
            note = "" if entry == target else f"  (symlink from {entry})"
            print(f"  ok  {target}{note}")

    if gaps:
        print(f"\n{len(gaps)} exec target(s) not covered by the profile:", file=sys.stderr)
        for entry, target in gaps:
            via = "" if entry == target else f", reached via {entry}"
            print(f"  - {target}{via}", file=sys.stderr)
        print(
            "\nAppArmor matches the resolved path, so add a rule for the target.", file=sys.stderr
        )
        return 1

    print(f"\nall {len(resolved)} exec targets are covered by {len(globs)} execute rules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
