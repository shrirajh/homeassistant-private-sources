"""Key file that wraps the unattended data encryption key.

Deliberately excluded from Home Assistant backups via backup_exclude, so a backup
archive on its own never contains a usable key.
"""

from __future__ import annotations

import os
from pathlib import Path

from .crypto import KEY_BYTES

KEY_FILENAME = "local.key"


class LocalKeystore:
    def __init__(self, directory: Path) -> None:
        self._path = directory / KEY_FILENAME

    @property
    def path(self) -> Path:
        return self._path

    def exists(self) -> bool:
        return self._path.is_file()

    def load(self) -> bytes:
        key = self._path.read_bytes()
        if len(key) != KEY_BYTES:
            raise ValueError(f"{self._path} is not a {KEY_BYTES} byte key")
        return key

    def create(self) -> bytes:
        key = os.urandom(KEY_BYTES)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Opened with the final mode so the key is never briefly world readable.
        # O_BINARY matters on Windows, where text mode would expand 0x0A to CRLF.
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0)
        handle = os.open(self._path, flags, 0o600)
        try:
            os.write(handle, key)
        finally:
            os.close(handle)
        return key

    def load_or_create(self) -> bytes:
        return self.load() if self.exists() else self.create()

    def destroy(self) -> None:
        self._path.unlink(missing_ok=True)
