"""Runtime settings resolved from the add-on environment."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SUPERVISOR_PEER = "172.30.32.2"
INGRESS_PORT = 8099

_TRUTHY = {"1", "true", "yes", "on"}


def _flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in _TRUTHY


def _path(name: str, default: Path) -> Path:
    raw = os.environ.get(name, "")
    return Path(raw).expanduser() if raw.strip() else default


def _options(data_dir: Path) -> dict[str, Any]:
    """Effective add-on options, written by the Supervisor before the container starts."""
    try:
        parsed = json.loads((data_dir / "options.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _resolve(options: dict[str, Any], key: str, env: str) -> Any:
    raw = os.environ.get(env)
    if raw is not None and raw.strip():
        return raw.strip()
    return options.get(key)


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in _TRUTHY


@dataclass(frozen=True)
class Settings:
    dev_mode: bool
    log_level: str
    host: str
    port: int
    data_dir: Path
    ha_config_dir: Path
    addons_dir: Path
    update_interval_hours: int
    auto_lock_minutes: int
    notify_on_update: bool
    supervisor_token: str | None

    @property
    def db_path(self) -> Path:
        return self.data_dir / "psm.db"

    @property
    def keystore_dir(self) -> Path:
        return self.data_dir / "keystore"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def known_hosts_path(self) -> Path:
        return self.data_dir / "known_hosts"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.keystore_dir.mkdir(parents=True, exist_ok=True)
        # The local key wraps the unattended DEK, so keep the directory owner-only.
        self.keystore_dir.chmod(0o700)


def load() -> Settings:
    dev_mode = _flag("PSM_DEV")
    dev_root = _path("PSM_DEV_ROOT", Path(".dev")).resolve()

    if dev_mode:
        data_dir = _path("PSM_DATA_DIR", dev_root / "data")
        ha_config_dir = _path("PSM_HA_CONFIG_DIR", dev_root / "homeassistant")
        addons_dir = _path("PSM_ADDONS_DIR", dev_root / "addons")
        host = os.environ.get("PSM_HOST", "127.0.0.1")
    else:
        data_dir = Path("/data")
        ha_config_dir = Path("/homeassistant")
        addons_dir = Path("/addons")
        host = "0.0.0.0"  # noqa: S104

    options = _options(data_dir)

    return Settings(
        dev_mode=dev_mode,
        log_level=str(_resolve(options, "log_level", "PSM_LOG_LEVEL") or "info").lower(),
        host=host,
        port=_as_int(os.environ.get("PSM_PORT"), INGRESS_PORT),
        data_dir=data_dir,
        ha_config_dir=ha_config_dir,
        addons_dir=addons_dir,
        update_interval_hours=_as_int(
            _resolve(options, "update_check_interval_hours", "PSM_UPDATE_INTERVAL_HOURS"), 6
        ),
        auto_lock_minutes=_as_int(
            _resolve(options, "auto_lock_minutes", "PSM_AUTO_LOCK_MINUTES"), 0
        ),
        notify_on_update=_as_bool(
            _resolve(options, "notify_on_update", "PSM_NOTIFY_ON_UPDATE"), True
        ),
        supervisor_token=os.environ.get("SUPERVISOR_TOKEN") or None,
    )
