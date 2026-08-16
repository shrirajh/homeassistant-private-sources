"""Option resolution from /data/options.json and environment overrides."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from psm import config

_OPTION_VARS = (
    "PSM_LOG_LEVEL",
    "PSM_UPDATE_INTERVAL_HOURS",
    "PSM_AUTO_LOCK_MINUTES",
    "PSM_NOTIFY_ON_UPDATE",
    "PSM_PORT",
    "PSM_DATA_DIR",
    "PSM_HA_CONFIG_DIR",
    "PSM_ADDONS_DIR",
    "PSM_HOST",
)


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for var in (*_OPTION_VARS, "SUPERVISOR_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("PSM_DEV", "1")
    monkeypatch.setenv("PSM_DEV_ROOT", str(tmp_path))
    return tmp_path / "data"


def _write_options(data_dir: Path, payload: dict) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "options.json").write_text(json.dumps(payload), encoding="utf-8")


def test_defaults_without_options_file(sandbox: Path) -> None:
    settings = config.load()
    assert settings.log_level == "info"
    assert settings.update_interval_hours == 6
    assert settings.auto_lock_minutes == 0
    assert settings.notify_on_update is True


def test_options_file_is_applied(sandbox: Path) -> None:
    _write_options(
        sandbox,
        {
            "log_level": "debug",
            "update_check_interval_hours": 24,
            "auto_lock_minutes": 15,
            "notify_on_update": False,
        },
    )
    settings = config.load()
    assert settings.log_level == "debug"
    assert settings.update_interval_hours == 24
    assert settings.auto_lock_minutes == 15
    assert settings.notify_on_update is False


def test_environment_overrides_options_file(sandbox: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_options(sandbox, {"log_level": "debug", "auto_lock_minutes": 15})
    monkeypatch.setenv("PSM_LOG_LEVEL", "error")
    monkeypatch.setenv("PSM_AUTO_LOCK_MINUTES", "30")
    settings = config.load()
    assert settings.log_level == "error"
    assert settings.auto_lock_minutes == 30


def test_malformed_options_file_falls_back_to_defaults(sandbox: Path) -> None:
    sandbox.mkdir(parents=True, exist_ok=True)
    (sandbox / "options.json").write_text("{not json", encoding="utf-8")
    settings = config.load()
    assert settings.log_level == "info"
    assert settings.notify_on_update is True


def test_non_numeric_option_falls_back(sandbox: Path) -> None:
    _write_options(sandbox, {"update_check_interval_hours": "soon"})
    assert config.load().update_interval_hours == 6


def test_production_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (*_OPTION_VARS, "PSM_DEV", "PSM_DEV_ROOT"):
        monkeypatch.delenv(var, raising=False)
    settings = config.load()
    assert settings.dev_mode is False
    assert settings.host == "0.0.0.0"
    assert settings.data_dir == Path("/data")
    assert settings.ha_config_dir == Path("/homeassistant")
    assert settings.addons_dir == Path("/addons")
    assert settings.db_path == Path("/data/psm.db")
    assert settings.keystore_dir == Path("/data/keystore")
