"""Root pytest configuration.

Qt links against ``libxkbcommon``, which is missing from some slim Linux
images. When that happens, and a compatible copy is bundled with another
installed wheel, this module creates the expected SONAME symlinks in a cache
directory and re-executes pytest once with ``LD_LIBRARY_PATH`` pointing at it.
If no copy can be found the user interface tests skip themselves and the rest
of the suite runs unaffected.
"""
from __future__ import annotations

import glob
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

#: Environment flag preventing an endless re-execution loop.
GUARD = "VDP_QT_LIBS_PREPARED"

#: SONAMEs Qt expects that may be absent from a minimal image.
REQUIRED_SONAMES = ("libxkbcommon.so.0", "libxkbcommon-x11.so.0")

#: Directories searched for a bundled copy of the missing libraries.
SEARCH_PATTERNS = (
    "/usr/local/lib/python*/site-packages/*.libs",
    f"{sys.prefix}/lib/python*/site-packages/*.libs",
    "/usr/lib/*-linux-gnu",
    "/usr/lib64",
)


def _qt_imports() -> bool:
    """Return ``True`` when PySide6 can be imported."""
    try:
        import PySide6.QtWidgets  # noqa: F401

        return True
    except Exception:  # noqa: BLE001 - any failure means Qt is unusable
        return False


def _find_library(soname: str) -> str | None:
    """Return a file providing *soname*, or ``None`` when there is none."""
    stem = soname.split(".so")[0]
    for pattern in SEARCH_PATTERNS:
        # Prefer an exact match, then a versioned copy bundled by a wheel.
        for candidate in sorted(glob.glob(f"{pattern}/{soname}")):
            if Path(candidate).is_file():
                return candidate
        for candidate in sorted(glob.glob(f"{pattern}/{stem}-*.so.*")):
            # ``libxkbcommon-x11-<hash>.so`` must not satisfy ``libxkbcommon``.
            name = Path(candidate).name[len(stem) + 1 :]
            if name.split(".so")[0].count("-") == 0 and Path(candidate).is_file():
                return candidate
    return None


def _prepare_qt_libraries() -> bool:
    """Create the SONAME symlinks; return ``True`` when they were created.

    Wheel-bundled libraries reference each other by their hashed file name, so
    every file of the providing directory is linked as well.
    """
    cache = ROOT / ".qt_libs"
    created = False
    for soname in REQUIRED_SONAMES:
        source = _find_library(soname)
        if source is None:
            continue
        cache.mkdir(parents=True, exist_ok=True)
        resolved = Path(source).resolve()
        for name in (soname, resolved.name):
            target = cache / name
            if not target.exists():
                try:
                    target.symlink_to(resolved)
                except OSError:
                    continue
        # Link only the related xkb libraries so the hashed DT_NEEDED entries
        # resolve, without shadowing Qt's own bundled libraries.
        for sibling in resolved.parent.glob("libxkb*.so*"):
            target = cache / sibling.name
            if not target.exists():
                try:
                    target.symlink_to(sibling.resolve())
                except OSError:
                    continue
        created = True
    if not created:
        return False
    existing = os.environ.get("LD_LIBRARY_PATH", "")
    os.environ["LD_LIBRARY_PATH"] = f"{cache}{os.pathsep}{existing}" if existing else str(cache)
    return True


if not _qt_imports() and not os.environ.get(GUARD):
    os.environ[GUARD] = "1"
    if _prepare_qt_libraries():
        # The dynamic loader reads LD_LIBRARY_PATH only at process start, so
        # the test session is restarted once with the prepared environment.
        os.execv(sys.executable, [sys.executable, "-m", "pytest", *sys.argv[1:]])
