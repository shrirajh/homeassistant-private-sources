"""SQLite storage for the vault, credentials and tracked repositories."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vault (
    tier       TEXT PRIMARY KEY CHECK (tier IN ('unattended', 'protected')),
    wrap_nonce BLOB NOT NULL,
    wrap_blob  BLOB NOT NULL,
    kdf        TEXT,
    kdf_salt   BLOB,
    kdf_n      INTEGER,
    kdf_r      INTEGER,
    kdf_p      INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS unlock_state (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until    REAL
);

CREATE TABLE IF NOT EXISTS credentials (
    id          TEXT PRIMARY KEY,
    label       TEXT NOT NULL,
    kind        TEXT NOT NULL CHECK (kind IN ('ssh', 'token')),
    tier        TEXT NOT NULL CHECK (tier IN ('unattended', 'protected')),
    username    TEXT,
    public_key  TEXT,
    fingerprint TEXT,
    nonce       BLOB NOT NULL,
    ciphertext  BLOB NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS repos (
    id                TEXT PRIMARY KEY,
    url               TEXT NOT NULL UNIQUE,
    host              TEXT NOT NULL,
    owner             TEXT NOT NULL,
    name              TEXT NOT NULL,
    category          TEXT NOT NULL,
    credential_id     TEXT REFERENCES credentials(id) ON DELETE SET NULL,
    ref_kind          TEXT NOT NULL DEFAULT 'tag',
    pinned_ref        TEXT,
    installed_ref     TEXT,
    installed_version TEXT,
    available_version TEXT,
    auto_update       INTEGER NOT NULL DEFAULT 0,
    hacs_json         TEXT,
    last_checked      TEXT,
    last_error        TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS installed_files (
    repo_id TEXT NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
    path    TEXT NOT NULL,
    sha256  TEXT NOT NULL,
    PRIMARY KEY (repo_id, path)
);

CREATE INDEX IF NOT EXISTS idx_repos_credential ON repos(credential_id);
"""


class Database:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(SCHEMA)
        self._conn.execute("INSERT OR IGNORE INTO unlock_state (id) VALUES (1)")

    def close(self) -> None:
        self._conn.close()

    def execute(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        return self._conn.execute(sql, params)

    def one(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Row | None:
        return self._conn.execute(sql, params).fetchone()

    def all(self, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
        return self._conn.execute(sql, params).fetchall()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        self._conn.execute("BEGIN")
        try:
            yield self._conn
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        self._conn.execute("COMMIT")
