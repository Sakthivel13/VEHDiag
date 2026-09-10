"""Centralised YAML configuration management.

The :class:`ConfigurationManager` merges three layers, later ones winning:

1. the built-in defaults hard-coded in :data:`BUILTIN_DEFAULTS`,
2. the YAML files shipped in ``config/``,
3. the per-user overrides stored in the platform application data directory.

Values are addressed with dotted paths::

    config.get("protocols.can.bitrate", 500000)
    config.set("ui.theme", "light")
"""
from __future__ import annotations

import copy
import os
import threading
from pathlib import Path
from typing import Any, Iterable

from ..utils.file_utils import ensure_dir, load_yaml, save_yaml
from ..utils.platform_utils import app_data_dir
from .event_bus import EventBus, EventType, get_event_bus

#: Directory containing the YAML files shipped with the application.
PACKAGE_CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"

#: Fallback configuration used when no YAML file is available at all.
BUILTIN_DEFAULTS: dict[str, Any] = {
    "application": {
        "name": "Vehicle Diagnostics Platform",
        "version": "0.1.0",
        "developer_mode": False,
        "auto_connect_last": False,
        "check_updates": False,
    },
    "connection": {
        "vci_type": "VIRTUAL",
        "channel": 0,
        "protocol": "CAN",
        "auto_reconnect": True,
        "reconnect_attempts": 3,
        "reconnect_delay_ms": 1000,
        "health_check_interval_ms": 5000,
    },
    "protocols": {
        "can": {
            "bitrate": 500000,
            "extended_id": False,
            "tx_id": 0x7E0,
            "rx_id": 0x7E8,
            "functional_id": 0x7DF,
            "padding_enabled": True,
            "padding_byte": 0x00,
        },
        "can_fd": {
            "bitrate": 500000,
            "data_bitrate": 2000000,
            "bitrate_switch": True,
        },
        "isotp": {
            "block_size": 8,
            "st_min_ms": 0,
            "n_bs_timeout_ms": 1000,
            "n_cr_timeout_ms": 1000,
            "n_ar_timeout_ms": 1000,
            "max_payload": 4095,
            "addressing_format": "NORMAL_11BIT",
        },
        "kline": {
            "port": "",
            "baudrate": 10400,
            "init_type": "FAST_INIT",
            "p1_ms": 5,
            "p2_ms": 50,
            "p3_ms": 55,
            "p4_ms": 5,
        },
        "doip": {
            "host": "192.168.0.10",
            "port": 13400,
            "source_address": 0x0E00,
            "target_address": 0x1000,
            "activation_type": 0x00,
            "use_tls": False,
            "alive_check_interval_ms": 2000,
        },
        "lin": {"baudrate": 19200, "nad": 0x01, "enhanced_checksum": True},
        "j1939": {"bitrate": 250000, "source_address": 0xF9},
        "flexray": {"config_file": "", "channels": "AB"},
    },
    "diagnostics": {
        "p2_client_ms": 150,
        "p2_star_client_ms": 5000,
        "s3_client_ms": 4000,
        "max_pending_responses": 20,
        "retry_on_busy": True,
        "max_retries": 3,
        "retry_delay_ms": 100,
        "tester_present_enabled": True,
        "tester_present_interval_ms": 2000,
        "tester_present_suppress_response": True,
        "suppress_positive_response": False,
    },
    "transfer": {
        "max_block_length": 0,
        "verify_after_transfer": True,
        "compression": "NONE",
        "encryption": "NONE",
        "gap_fill_byte": 0xFF,
    },
    "logging": {
        "level": "INFO",
        "log_to_file": True,
        "log_to_database": True,
        "directory": "",
        "database_path": "",
        "max_file_size_mb": 50,
        "backup_count": 10,
        "retention_days": 30,
        "flush_interval_ms": 100,
        "buffer_size": 500,
        "hide_tester_present": False,
    },
    "ui": {
        "theme": "dark",
        "accent_color": "#7C3AED",
        "font_family": "Roboto",
        "monospace_family": "Roboto Mono",
        "base_font_pt": 13,
        "dpi_scaling": "auto",
        "remember_geometry": True,
            "start_maximized": True,
        "show_splash": True,
        "toast_timeout_ms": 4000,
        "log_panel_visible": True,
        "analysis_panel_visible": True,
    },
    "paths": {
        "test_scripts": "sample_test_scripts",
        "firmware": "",
        "exports": "",
        "profiles": "",
    },
    "plugins": {"enabled": True, "directories": ["plugins"], "disabled": []},
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge *override* into a copy of *base*."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


class ConfigurationManager:
    """Loads, merges, validates and persists the application configuration."""

    #: Names of the YAML documents loaded into their own namespace.
    NAMESPACED_FILES = {
        "protocol_definitions": "protocol_definitions.yaml",
        "sid_definitions": "sid_definitions.yaml",
        "did_definitions": "did_definitions.yaml",
        "dtc_definitions": "dtc_definitions.yaml",
        "nrc_definitions": "nrc_definitions.yaml",
    }

    def __init__(
        self,
        config_dir: str | Path | None = None,
        user_config: str | Path | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        """Create the manager and load every configuration layer.

        Args:
            config_dir: Directory holding the shipped YAML files. Defaults to
                ``$VDP_CONFIG_DIR`` or the packaged ``config/`` folder.
            user_config: Path of the writable user override file.
            event_bus: Bus used to announce configuration changes.
        """
        env_dir = os.environ.get("VDP_CONFIG_DIR")
        self.config_dir = Path(config_dir or env_dir or PACKAGE_CONFIG_DIR).expanduser()
        self.user_config_path = Path(
            user_config or app_data_dir() / "user_config.yaml"
        ).expanduser()
        self._bus = event_bus or get_event_bus()
        self._lock = threading.RLock()
        self._data: dict[str, Any] = copy.deepcopy(BUILTIN_DEFAULTS)
        self._definitions: dict[str, Any] = {}
        self.reload()

    # -- loading and saving -------------------------------------------------
    def reload(self) -> None:
        """Re-read every configuration layer from disk."""
        with self._lock:
            data = copy.deepcopy(BUILTIN_DEFAULTS)
            shipped = load_yaml(self.config_dir / "default_config.yaml", default={}) or {}
            data = _deep_merge(data, shipped)
            user = load_yaml(self.user_config_path, default={}) or {}
            data = _deep_merge(data, user)
            self._data = _deep_merge(data, self._environment_overrides())
            self._definitions = {
                key: (load_yaml(self.config_dir / name, default={}) or {})
                for key, name in self.NAMESPACED_FILES.items()
            }

    def save(self, path: str | Path | None = None) -> Path:
        """Persist the current configuration as the user override file."""
        target = Path(path or self.user_config_path)
        ensure_dir(target.parent)
        with self._lock:
            save_yaml(target, self._data)
        return target

    def reset_to_defaults(self) -> None:
        """Discard user overrides and reload the shipped defaults."""
        with self._lock:
            self._data = _deep_merge(
                copy.deepcopy(BUILTIN_DEFAULTS),
                load_yaml(self.config_dir / "default_config.yaml", default={}) or {},
            )
        self._bus.publish(EventType.SYSTEM_CONFIG_CHANGED, {"reset": True}, "ConfigurationManager")

    # -- value access ---------------------------------------------------------
    def get(self, path: str, default: Any = None) -> Any:
        """Return the value at the dotted *path*.

        Example:
            >>> cfg = ConfigurationManager(user_config="/tmp/vdp_none.yaml")
            >>> cfg.get("protocols.can.bitrate")
            500000
        """
        with self._lock:
            node: Any = self._data
            for part in path.split("."):
                if not isinstance(node, dict) or part not in node:
                    return default
                node = node[part]
            return copy.deepcopy(node) if isinstance(node, (dict, list)) else node

    def set(self, path: str, value: Any, *, publish: bool = True) -> None:
        """Assign *value* at the dotted *path*, creating intermediate levels."""
        parts = path.split(".")
        with self._lock:
            node = self._data
            for part in parts[:-1]:
                node = node.setdefault(part, {})
                if not isinstance(node, dict):
                    raise TypeError(f"cannot descend into non-mapping at {part!r}")
            old = node.get(parts[-1])
            node[parts[-1]] = value
        if publish and old != value:
            self._bus.publish(
                EventType.SYSTEM_CONFIG_CHANGED,
                {"path": path, "old": old, "new": value},
                "ConfigurationManager",
            )

    def update(self, values: dict[str, Any]) -> None:
        """Apply a mapping of dotted paths to values."""
        for path, value in values.items():
            self.set(path, value)

    def section(self, path: str) -> dict[str, Any]:
        """Return a deep copy of the mapping at *path* (empty when missing)."""
        value = self.get(path, {})
        return value if isinstance(value, dict) else {}

    def as_dict(self) -> dict[str, Any]:
        """Return a deep copy of the entire configuration."""
        with self._lock:
            return copy.deepcopy(self._data)

    # -- definition tables --------------------------------------------------------
    def definitions(self, name: str) -> dict[str, Any]:
        """Return one of the loaded definition documents by key."""
        return copy.deepcopy(self._definitions.get(name, {}))

    def did_definitions(self) -> dict[int, dict[str, Any]]:
        """Return the DID definition table keyed by integer identifier."""
        raw = self._definitions.get("did_definitions", {}).get("dids", {}) or {}
        result: dict[int, dict[str, Any]] = {}
        for key, value in raw.items():
            did = int(str(key), 16) if isinstance(key, str) else int(key)
            result[did] = dict(value or {})
        return result

    def nrc_definitions(self) -> dict[int, dict[str, Any]]:
        """Return the NRC definition table keyed by integer code."""
        raw = self._definitions.get("nrc_definitions", {}).get("nrcs", {}) or {}
        return {
            (int(str(k), 16) if isinstance(k, str) else int(k)): dict(v or {})
            for k, v in raw.items()
        }

    def vci_profile(self, name: str) -> dict[str, Any]:
        """Load one of the ``config/vci_profiles/*.yaml`` documents."""
        return load_yaml(self.config_dir / "vci_profiles" / f"{name}.yaml", default={}) or {}

    def session_template(self, name: str) -> dict[str, Any]:
        """Load one of the ``config/session_templates/*.yaml`` documents."""
        return load_yaml(self.config_dir / "session_templates" / f"{name}.yaml", default={}) or {}

    def available_vci_profiles(self) -> list[str]:
        """Return the names of the shipped VCI profiles."""
        directory = self.config_dir / "vci_profiles"
        if not directory.exists():
            return []
        return sorted(p.stem for p in directory.glob("*.yaml"))

    def theme_path(self, theme: str) -> Path:
        """Return the path of a QSS theme file shipped in ``config/themes``."""
        return self.config_dir / "themes" / f"{theme}_theme.qss"

    # -- helpers ---------------------------------------------------------------------
    def _environment_overrides(self) -> dict[str, Any]:
        """Translate ``VDP_*`` environment variables into configuration values."""
        overrides: dict[str, Any] = {}
        mapping: Iterable[tuple[str, str, type]] = (
            ("VDP_LOG_LEVEL", "logging.level", str),
            ("VDP_LOG_DIR", "logging.directory", str),
            ("VDP_DB_PATH", "logging.database_path", str),
            ("VDP_DEFAULT_VCI", "connection.vci_type", str),
            ("VDP_THEME", "ui.theme", str),
            ("VDP_DEVELOPER_MODE", "application.developer_mode", bool),
        )
        for env_name, path, kind in mapping:
            raw = os.environ.get(env_name)
            if raw is None or raw == "":
                continue
            value: Any = raw
            if kind is bool:
                value = raw.strip().lower() in {"1", "true", "yes", "on"}
            node = overrides
            parts = path.split(".")
            for part in parts[:-1]:
                node = node.setdefault(part, {})
            node[parts[-1]] = value
        return overrides

    def __repr__(self) -> str:  # noqa: D105 - trivial
        return f"<ConfigurationManager dir={self.config_dir} keys={list(self._data)}>"


_INSTANCE: ConfigurationManager | None = None
_INSTANCE_LOCK = threading.Lock()


def get_config() -> ConfigurationManager:
    """Return the process wide :class:`ConfigurationManager`."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = ConfigurationManager()
    return _INSTANCE


def set_config(manager: ConfigurationManager | None) -> None:
    """Override (or clear) the global configuration manager, used in tests."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = manager


__all__ = [
    "BUILTIN_DEFAULTS",
    "PACKAGE_CONFIG_DIR",
    "ConfigurationManager",
    "get_config",
    "set_config",
]
