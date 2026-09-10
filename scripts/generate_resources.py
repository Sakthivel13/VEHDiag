#!/usr/bin/env python3
"""Generate the SVG icon set, the QSS templates and the Qt resource file.

Usage::

    python scripts/generate_resources.py                # icons + qrc
    python scripts/generate_resources.py --stylesheets  # also rewrite the QSS
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "ui" / "resources" / "icons"
FONT_DIR = ROOT / "ui" / "resources" / "fonts"
IMAGE_DIR = ROOT / "ui" / "resources" / "images"
QRC_PATH = ROOT / "ui" / "resources" / "resources.qrc"
STYLE_DIR = ROOT / "ui" / "styles"

#: Header prepended to every generated stylesheet.
QSS_HEADER = """/* ============================================================================
 * Vehicle Diagnostics Platform - {label} theme
 *
 * This file is the *baseline* stylesheet of the {label} theme, generated at a
 * reference DPI scale of 1.0 (96 DPI). At runtime
 * :class:`ui.theme_manager.ThemeManager` regenerates the same rules with the
 * real DPI scale so paddings and radii follow the screen; this file is used
 * as a fallback, as a starting point for custom themes and as the reference
 * when reviewing the palette.
 *
 * Palette (from the design specification):
{palette}
 *
 * Regenerate with:  python scripts/generate_resources.py --stylesheets
 * ==========================================================================*/
"""


def build_qrc() -> Path:
    """Write ``resources.qrc`` listing every bundled asset."""
    entries: list[str] = []
    for directory, prefix in ((ICON_DIR, "icons"), (FONT_DIR, "fonts"), (IMAGE_DIR, "images")):
        files = sorted(p.name for p in directory.glob("*") if p.is_file())
        if not files:
            continue
        rows = "\n".join(f"        <file>{prefix}/{name}</file>" for name in files)
        entries.append(f'    <qresource prefix="/{prefix}">\n{rows}\n    </qresource>')
    QRC_PATH.write_text("<RCC>\n" + "\n".join(entries) + "\n</RCC>\n", encoding="utf-8")
    return QRC_PATH


def compile_qrc() -> bool:
    """Compile the resource file with ``pyside6-rcc`` when it is available."""
    target = ROOT / "ui" / "resources" / "resources_rc.py"
    try:
        subprocess.run(
            ["pyside6-rcc", str(QRC_PATH), "-o", str(target)], check=True, cwd=ROOT
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("pyside6-rcc is unavailable; the icons are loaded from disk instead")
        return False
    print(f"compiled {target}")
    return True


def build_stylesheets() -> list[Path]:
    """Regenerate the shipped ``*.qss`` templates from the theme manager.

    The generated files are the baseline of each theme at a DPI scale of 1.0.
    ``custom_widgets.qss`` is hand written and is never overwritten.

    Returns:
        The paths that were written.
    """
    sys.path.insert(0, str(ROOT))
    from PySide6.QtWidgets import QApplication  # noqa: PLC0415 - optional dependency

    from ui.dpi_scaler import DPIScaler  # noqa: PLC0415
    from ui.styles import QSS_FILES  # noqa: PLC0415
    from ui.theme_manager import ThemeManager  # noqa: PLC0415

    application = QApplication.instance() or QApplication([])
    scaler = DPIScaler()
    written: list[Path] = []
    for theme, filename in QSS_FILES.items():
        manager = ThemeManager(scaler=scaler)
        manager.set_theme(theme)
        palette = "\n".join(
            f" *   {key:<16} {value}"
            for key, value in manager.colors().items()
            if isinstance(value, str) and value.startswith("#")
        )
        header = QSS_HEADER.format(label=theme.replace("_", " "), palette=palette)
        target = STYLE_DIR / filename
        target.write_text(header + manager.stylesheet() + "\n", encoding="utf-8")
        written.append(target)
        print(f"stylesheet: {target.name} ({target.stat().st_size} bytes)")
    del application
    return written


def main(argv: list[str] | None = None) -> int:
    """Generate the resource file and optionally the stylesheets."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stylesheets",
        action="store_true",
        help="also regenerate the shipped QSS theme templates",
    )
    args = parser.parse_args(argv)

    print(f"icons   : {len(list(ICON_DIR.glob('*.svg')))}")
    print(f"written : {build_qrc()}")
    compile_qrc()
    if args.stylesheets:
        build_stylesheets()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
