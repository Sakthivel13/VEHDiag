"""Operating system specific helpers."""
from __future__ import annotations

import ctypes
import os
import platform
import sys
from pathlib import Path


def is_windows() -> bool:
    """Return ``True`` on Microsoft Windows."""
    return sys.platform.startswith("win")


def is_linux() -> bool:
    """Return ``True`` on Linux."""
    return sys.platform.startswith("linux")


def is_macos() -> bool:
    """Return ``True`` on macOS."""
    return sys.platform == "darwin"


def shared_library_suffix() -> str:
    """Return the platform's shared library extension."""
    if is_windows():
        return ".dll"
    if is_macos():
        return ".dylib"
    return ".so"


def library_candidates(base_name: str) -> list[str]:
    """Return plausible file names for a vendor library called *base_name*.

    Example:
        >>> "PCANBasic.dll" in library_candidates("PCANBasic") or True
        True
    """
    suffix = shared_library_suffix()
    names = [f"{base_name}{suffix}"]
    if not is_windows():
        names.append(f"lib{base_name.lower()}{suffix}")
        names.append(f"lib{base_name}{suffix}")
    return names


def load_shared_library(base_name: str, extra_paths: list[str] | None = None) -> ctypes.CDLL | None:
    """Try to load a vendor shared library.

    Args:
        base_name: Library name without prefix/suffix, e.g. ``"PCANBasic"``.
        extra_paths: Additional directories to search before the system paths.

    Returns:
        The loaded library, or ``None`` when it is not installed.
    """
    candidates: list[str] = []
    for directory in extra_paths or []:
        for name in library_candidates(base_name):
            candidates.append(str(Path(directory) / name))
    candidates.extend(library_candidates(base_name))
    loader = ctypes.WinDLL if is_windows() and hasattr(ctypes, "WinDLL") else ctypes.CDLL
    for candidate in candidates:
        try:
            return loader(candidate)  # type: ignore[operator]
        except OSError:
            continue
    return None


def app_data_dir(app_name: str = "VehicleDiagnosticsPlatform") -> Path:
    """Return the per-user writable configuration directory."""
    if is_windows():
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif is_macos():
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    path = base / app_name
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_dir(app_name: str = "VehicleDiagnosticsPlatform") -> Path:
    """Return the per-user writable log directory."""
    path = app_data_dir(app_name) / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def system_info() -> dict[str, str]:
    """Return a mapping describing the runtime environment (About dialog)."""
    return {
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python": platform.python_version(),
        "python_build": " ".join(platform.python_build()),
        "executable": sys.executable,
    }


def list_serial_ports() -> list[str]:
    """Return the device names of available serial ports.

    Returns an empty list when :mod:`pyserial` is not installed.
    """
    try:
        from serial.tools import list_ports  # type: ignore[import-not-found]
    except ImportError:
        return []
    return [port.device for port in list_ports.comports()]


__all__ = [
    "is_windows",
    "is_linux",
    "is_macos",
    "shared_library_suffix",
    "library_candidates",
    "load_shared_library",
    "app_data_dir",
    "log_dir",
    "system_info",
    "list_serial_ports",
]
