"""Fixtures for the Qt based user interface tests.

Qt needs a few system libraries that are not always installed. The helper
below pre-loads them from wherever they can be found so the tests also run on
minimal container images; when nothing is found the whole module is skipped.
"""
from __future__ import annotations

import ctypes
import glob
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def preload_system_libraries() -> None:
    """Pre-load the shared libraries Qt links against.

    Some slim Linux images ship without ``libxkbcommon``; other Python wheels
    (for example OpenCV) bundle a copy that Qt can use.
    """
    for name in ("libxkbcommon.so.0", "libxkbcommon-x11.so.0"):
        try:
            ctypes.CDLL(name)
            continue
        except OSError:
            pass
        pattern = str(Path(sys.prefix) / "lib" / "python*" / "site-packages" / "*.libs" / name.replace(".so.0", "*.so.*"))
        for candidate in glob.glob(pattern) + glob.glob(f"/usr/local/lib/python*/site-packages/*.libs/{name.split('.so')[0]}-*.so.*"):
            try:
                ctypes.CDLL(candidate)
                break
            except OSError:
                continue


preload_system_libraries()

pytest.importorskip("PySide6", reason="PySide6 (and its system libraries) are required")


@pytest.fixture()
def scaler():
    """Return a DPI scaler at 100% scaling."""
    from ui.dpi_scaler import DPIScaler, ScreenMetrics

    return DPIScaler(ScreenMetrics(width=1920, height=1080, dpi=96.0))


@pytest.fixture()
def main_window(qtbot, config, event_bus):
    """Return a fully built main window."""
    from src.diagnostics.services.data_services.read_data_by_id import build_registry
    from ui.main_window import MainWindow

    window = MainWindow(config, event_bus, build_registry(config.did_definitions()))
    qtbot.addWidget(window)
    window.resize(1920, 1080)
    return window
