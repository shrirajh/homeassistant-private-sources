"""git plumbing.

Credentials never reach argv, .git/config, or a log line. SSH keys are written to
tmpfs for the duration of a single call and removed afterwards; tokens are handed
to git through GIT_ASKPASS so they never appear in a process listing.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shlex
import shutil
import tarfile
import tempfile
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from .credentials import CredentialKind
from .sshkeys import InvalidKeyMaterial
from .sshkeys import fingerprint as key_fingerprint

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 180
PACKAGE_DIR = Path(__file__).parent
ASKPASS = PACKAGE_DIR / "bin" / "askpass.sh"
BUNDLED_KNOWN_HOSTS = PACKAGE_DIR / "known_hosts"

_CREDENTIALS_IN_URL = re.compile(r"(?<=//)[^/@\s]+(?=@)")
_HOST_KEY_MARKERS = ("Host key verification failed", "REMOTE HOST IDENTIFICATION HAS CHANGED")


class GitError(Exception):
    def __init__(self, message: str, *, stderr: str = "") -> None:
        super().__init__(message)
        self.stderr = stderr


class HostKeyUnknown(GitError):
    """The remote host is not present in either known_hosts file."""


@dataclass(frozen=True)
class Auth:
    kind: CredentialKind
    secret: bytes
    username: str | None = None


@dataclass(frozen=True)
class Ref:
    name: str
    kind: str
    sha: str

    def as_dict(self) -> dict[str, str]:
        return {"name": self.name, "kind": self.kind, "sha": self.sha}


def redact(text: str) -> str:
    return _CREDENTIALS_IN_URL.sub("***", text)


def _summarise(stderr: str) -> str:
    for line in reversed(stderr.splitlines()):
        cleaned = line.strip()
        if cleaned and not cleaned.startswith("Warning:"):
            return cleaned.removeprefix("fatal: ").removeprefix("error: ")
    return ""


def _write_private_key(path: Path, material: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0)
    handle = os.open(path, flags, 0o600)
    try:
        os.write(handle, material if material.endswith(b"\n") else material + b"\n")
    finally:
        os.close(handle)


class Git:
    def __init__(self, cache_dir: Path, known_hosts: Path, timeout: int = DEFAULT_TIMEOUT) -> None:
        self._cache_dir = cache_dir
        self._known_hosts = known_hosts
        self._timeout = timeout
        self._locks: dict[str, asyncio.Lock] = {}

    def mirror_path(self, repo_id: str) -> Path:
        return self._cache_dir / f"{repo_id}.git"

    def has_mirror(self, repo_id: str) -> bool:
        return (self.mirror_path(repo_id) / "HEAD").is_file()

    async def ls_remote(self, url: str, auth: Auth | None = None) -> list[Ref]:
        """Discover refs without cloning. Works on every host, including plain git."""
        out = await self._text(["git", "ls-remote", "--refs", "--tags", "--heads", url], auth=auth)
        refs: list[Ref] = []
        for line in out.splitlines():
            sha, _, ref = line.partition("\t")
            if ref.startswith("refs/tags/"):
                refs.append(Ref(ref.removeprefix("refs/tags/"), "tag", sha.strip()))
            elif ref.startswith("refs/heads/"):
                refs.append(Ref(ref.removeprefix("refs/heads/"), "branch", sha.strip()))
        return refs

    async def mirror(self, repo_id: str, url: str, auth: Auth | None = None) -> Path:
        path = self.mirror_path(repo_id)
        async with self._locks.setdefault(repo_id, asyncio.Lock()):
            if self.has_mirror(repo_id):
                await self._text(
                    ["git", "--git-dir", str(path), "remote", "set-url", "origin", url]
                )
                await self._text(
                    ["git", "--git-dir", str(path), "remote", "update", "--prune"], auth=auth
                )
            else:
                if path.exists():
                    shutil.rmtree(path, ignore_errors=True)
                path.parent.mkdir(parents=True, exist_ok=True)
                await self._text(["git", "clone", "--quiet", "--mirror", url, str(path)], auth=auth)
        return path

    async def local_refs(self, repo_id: str) -> list[Ref]:
        out = await self._text(
            [
                "git",
                "--git-dir",
                str(self.mirror_path(repo_id)),
                "for-each-ref",
                "--format=%(objectname)\t%(refname)",
                "refs/tags",
                "refs/heads",
            ]
        )
        refs: list[Ref] = []
        for line in out.splitlines():
            sha, _, ref = line.partition("\t")
            if ref.startswith("refs/tags/"):
                refs.append(Ref(ref.removeprefix("refs/tags/"), "tag", sha.strip()))
            elif ref.startswith("refs/heads/"):
                refs.append(Ref(ref.removeprefix("refs/heads/"), "branch", sha.strip()))
        return refs

    async def default_branch(self, repo_id: str) -> str:
        try:
            out = await self._text(
                [
                    "git",
                    "--git-dir",
                    str(self.mirror_path(repo_id)),
                    "symbolic-ref",
                    "--short",
                    "HEAD",
                ]
            )
        except GitError:
            return "main"
        return out.strip() or "main"

    async def resolve(self, repo_id: str, ref: str) -> str:
        out = await self._text(
            ["git", "--git-dir", str(self.mirror_path(repo_id)), "rev-parse", f"{ref}^{{commit}}"]
        )
        return out.strip()

    async def ls_tree(self, repo_id: str, ref: str) -> list[str]:
        out = await self._text(
            [
                "git",
                "--git-dir",
                str(self.mirror_path(repo_id)),
                "ls-tree",
                "-r",
                "--name-only",
                ref,
            ]
        )
        return [line for line in out.splitlines() if line]

    async def show(self, repo_id: str, ref: str, path: str) -> bytes:
        return await self._run(
            ["git", "--git-dir", str(self.mirror_path(repo_id)), "show", f"{ref}:{path}"]
        )

    async def export(self, repo_id: str, ref: str, dest: Path) -> None:
        """Materialise a ref into dest with no .git directory."""
        dest.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="psm-export-") as tmp:
            archive = Path(tmp) / "tree.tar"
            await self._text(
                [
                    "git",
                    "--git-dir",
                    str(self.mirror_path(repo_id)),
                    "archive",
                    "--format=tar",
                    f"--output={archive}",
                    ref,
                ]
            )
            with tarfile.open(archive) as tar:
                # The data filter rejects absolute paths, traversal and special files.
                tar.extractall(dest, filter="data")

    async def scan_host(self, host: str, port: int = 22) -> list[dict[str, str]]:
        out = await self._text(["ssh-keyscan", "-p", str(port), "-T", "10", host])
        entries: list[dict[str, str]] = []
        for line in out.splitlines():
            parts = line.split()
            if line.startswith("#") or len(parts) < 3:
                continue
            try:
                digest = key_fingerprint(f"{parts[1]} {parts[2]}")
            except InvalidKeyMaterial:
                continue
            entries.append({"line": line, "type": parts[1], "fingerprint": digest})
        return entries

    def trust_host(self, lines: Sequence[str]) -> int:
        self._known_hosts.parent.mkdir(parents=True, exist_ok=True)
        existing = (
            self._known_hosts.read_text(encoding="utf-8").splitlines()
            if self._known_hosts.exists()
            else []
        )
        added = 0
        with self._known_hosts.open("a", encoding="utf-8") as handle:
            for line in lines:
                cleaned = line.strip()
                if cleaned and cleaned not in existing:
                    handle.write(cleaned + "\n")
                    added += 1
        return added

    def forget_mirror(self, repo_id: str) -> None:
        shutil.rmtree(self.mirror_path(repo_id), ignore_errors=True)

    def _ssh_command(self, key_path: Path | None) -> str:
        known = f"{BUNDLED_KNOWN_HOSTS} {self._known_hosts}"
        parts = [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            f"UserKnownHostsFile={known}",
            "-o",
            "IdentitiesOnly=yes",
            "-o",
            "IdentityAgent=none",
            "-o",
            "ConnectTimeout=20",
        ]
        if key_path is not None:
            parts += ["-i", str(key_path)]
        return " ".join(shlex.quote(part) for part in parts)

    @asynccontextmanager
    async def _environment(self, auth: Auth | None) -> AsyncIterator[dict[str, str]]:
        with tempfile.TemporaryDirectory(prefix="psm-git-") as tmp:
            workdir = Path(tmp)
            env = {
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "HOME": str(workdir),
                "LC_ALL": "C",
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": os.devnull,
            }
            if auth is not None and auth.kind is CredentialKind.SSH:
                key_path = workdir / "id"
                _write_private_key(key_path, auth.secret)
                env["GIT_SSH_COMMAND"] = self._ssh_command(key_path)
            elif auth is not None and auth.kind is CredentialKind.TOKEN:
                env["GIT_ASKPASS"] = str(ASKPASS)
                env["PSM_GIT_USERNAME"] = auth.username or "x-access-token"
                env["PSM_GIT_PASSWORD"] = auth.secret.decode("utf-8")
            else:
                env["GIT_SSH_COMMAND"] = self._ssh_command(None)
            yield env

    async def _run(self, args: Sequence[str], *, auth: Auth | None = None) -> bytes:
        async with self._environment(auth) as env:
            process = await asyncio.create_subprocess_exec(
                *args,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), self._timeout)
            except TimeoutError:
                process.kill()
                await process.wait()
                raise GitError(f"{args[0]} timed out after {self._timeout}s") from None

        if process.returncode != 0:
            detail = redact(stderr.decode("utf-8", errors="replace").strip())
            _LOGGER.debug("%s failed: %s", args[0], detail)
            if any(marker in detail for marker in _HOST_KEY_MARKERS):
                raise HostKeyUnknown("host key is not trusted", stderr=detail)
            raise GitError(
                _summarise(detail) or f"{args[0]} exited {process.returncode}", stderr=detail
            )
        return stdout

    async def _text(self, args: Sequence[str], *, auth: Auth | None = None) -> str:
        return (await self._run(args, auth=auth)).decode("utf-8", errors="replace")
