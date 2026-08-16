"""git plumbing, exercised against a real local repository."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from psm.credentials import CredentialKind
from psm.gitops import Auth, Git, GitError, redact

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
def source(tmp_path: Path) -> Path:
    repo = tmp_path / "source"
    (repo / "custom_components" / "demo").mkdir(parents=True)
    (repo / "custom_components" / "demo" / "manifest.json").write_text(
        '{"domain": "demo", "version": "1.0.0"}', encoding="utf-8"
    )
    (repo / "hacs.json").write_text('{"name": "Demo"}', encoding="utf-8")
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "initial")
    _git(repo, "tag", "v1.0.0")
    return repo


@pytest.fixture
def git(tmp_path: Path) -> Git:
    return Git(cache_dir=tmp_path / "cache", known_hosts=tmp_path / "data" / "known_hosts")


async def test_ls_remote_lists_tags_and_branches(git: Git, source: Path) -> None:
    refs = await git.ls_remote(str(source))

    assert {r.name for r in refs if r.kind == "tag"} == {"v1.0.0"}
    assert {r.name for r in refs if r.kind == "branch"} == {"main"}
    assert all(len(r.sha) == 40 for r in refs)


async def test_mirror_then_update(git: Git, source: Path) -> None:
    await git.mirror("repo1", str(source))
    assert git.has_mirror("repo1")
    assert {r.name for r in await git.local_refs("repo1") if r.kind == "tag"} == {"v1.0.0"}

    (source / "extra.txt").write_text("more", encoding="utf-8")
    _git(source, "add", "-A")
    _git(source, "commit", "-q", "-m", "second")
    _git(source, "tag", "v1.1.0")

    await git.mirror("repo1", str(source))
    assert {r.name for r in await git.local_refs("repo1") if r.kind == "tag"} == {
        "v1.0.0",
        "v1.1.0",
    }


async def test_resolve_and_default_branch(git: Git, source: Path) -> None:
    await git.mirror("repo1", str(source))

    sha = await git.resolve("repo1", "v1.0.0")
    assert len(sha) == 40
    assert await git.default_branch("repo1") == "main"


async def test_ls_tree_and_show(git: Git, source: Path) -> None:
    await git.mirror("repo1", str(source))

    files = await git.ls_tree("repo1", "v1.0.0")
    assert "hacs.json" in files
    assert "custom_components/demo/manifest.json" in files

    assert b'"name": "Demo"' in await git.show("repo1", "v1.0.0", "hacs.json")


async def test_export_produces_a_clean_tree(git: Git, source: Path, tmp_path: Path) -> None:
    await git.mirror("repo1", str(source))
    dest = tmp_path / "export"

    await git.export("repo1", "v1.0.0", dest)

    assert (dest / "hacs.json").is_file()
    assert (dest / "custom_components" / "demo" / "manifest.json").is_file()
    assert not (dest / ".git").exists()


async def test_export_at_an_older_tag(git: Git, source: Path, tmp_path: Path) -> None:
    (source / "extra.txt").write_text("more", encoding="utf-8")
    _git(source, "add", "-A")
    _git(source, "commit", "-q", "-m", "second")
    _git(source, "tag", "v1.1.0")
    await git.mirror("repo1", str(source))

    old = tmp_path / "old"
    await git.export("repo1", "v1.0.0", old)
    assert not (old / "extra.txt").exists()

    new = tmp_path / "new"
    await git.export("repo1", "v1.1.0", new)
    assert (new / "extra.txt").is_file()


async def test_unknown_remote_raises(git: Git, tmp_path: Path) -> None:
    with pytest.raises(GitError):
        await git.ls_remote(str(tmp_path / "does-not-exist"))


async def test_unknown_ref_raises(git: Git, source: Path) -> None:
    await git.mirror("repo1", str(source))
    with pytest.raises(GitError):
        await git.resolve("repo1", "v9.9.9")


async def test_forget_mirror(git: Git, source: Path) -> None:
    await git.mirror("repo1", str(source))
    git.forget_mirror("repo1")
    assert not git.has_mirror("repo1")


def test_ssh_command_pins_known_hosts(git: Git, tmp_path: Path) -> None:
    command = git._ssh_command(tmp_path / "key")

    assert "BatchMode=yes" in command
    assert "StrictHostKeyChecking=yes" in command
    assert "IdentitiesOnly=yes" in command
    assert "known_hosts" in command


def test_ssh_key_never_reaches_argv(git: Git, tmp_path: Path) -> None:
    """The key path is passed to ssh, but the key material itself only hits tmpfs."""
    key_path = tmp_path / "psm-git-abc" / "id"
    command = git._ssh_command(key_path)

    assert "BEGIN OPENSSH" not in command
    assert str(key_path) in command


async def test_token_auth_uses_askpass(git: Git) -> None:
    auth = Auth(kind=CredentialKind.TOKEN, secret=b"ghp_secret", username="x-access-token")

    async with git._environment(auth) as env:
        assert env["GIT_ASKPASS"].endswith("askpass.sh")
        assert env["PSM_GIT_USERNAME"] == "x-access-token"
        assert env["PSM_GIT_PASSWORD"] == "ghp_secret"
        assert env["GIT_TERMINAL_PROMPT"] == "0"


async def test_ssh_auth_writes_key_to_a_temporary_file(git: Git) -> None:
    auth = Auth(kind=CredentialKind.SSH, secret=b"-----BEGIN OPENSSH PRIVATE KEY-----")

    async with git._environment(auth) as env:
        command = env["GIT_SSH_COMMAND"]
        key_path = Path(command.split("-i")[-1].strip().strip("'\""))
        assert key_path.is_file()
        assert key_path.read_bytes().startswith(b"-----BEGIN OPENSSH")

    assert not key_path.exists()


def test_trust_host_appends_without_duplicates(git: Git) -> None:
    line = "example.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExample"

    assert git.trust_host([line]) == 1
    assert git.trust_host([line]) == 0
    assert git._known_hosts.read_text(encoding="utf-8").count(line) == 1


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://user:ghp_tok@github.com/a/b.git", "https://***@github.com/a/b.git"),
        ("fatal: could not read from https://x-access-token:s3cret@gitlab.com/a", "***@gitlab.com"),
        ("git@github.com:a/b.git", "git@github.com:a/b.git"),
    ],
)
def test_redact_strips_inline_credentials(raw: str, expected: str) -> None:
    assert expected in redact(raw)
