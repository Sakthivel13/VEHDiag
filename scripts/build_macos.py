#!/usr/bin/env python3
"""Build a macOS application bundle with PyInstaller."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Data directories bundled with the executable.
DATA_DIRS = ("config", "ui/resources", "sample_test_scripts", "plugins", "docs")

#: Modules PyInstaller cannot discover on its own.
HIDDEN_IMPORTS = (
    "can.interfaces.socketcan",
    "can.interfaces.pcan",
    "can.interfaces.kvaser",
    "can.interfaces.vector",
    "serial.tools.list_ports",
    "PySide6.QtSvg",
)


def build(one_file: bool = False, clean: bool = True) -> Path:
    """Run PyInstaller and return the output directory.

    Args:
        one_file: Produce a single executable instead of a directory.
        clean: Remove the previous build artefacts first.
    """
    if clean:
        for directory in ("build", "dist"):
            shutil.rmtree(ROOT / directory, ignore_errors=True)

    command = [
        sys.executable, "-m", "PyInstaller",
        "--name", "VehicleDiagnosticsPlatform",
        "--onefile" if one_file else "--onedir",
        "--windowed",
        "--noconfirm",
        "--osx-bundle-identifier", "com.vdp.diagnostics",
        "--icon", str(ROOT / "ui/resources/images/app_icon.icns"),
    ]
    for directory in DATA_DIRS:
        source = ROOT / directory
        if source.exists():
            command += ["--add-data", f"{source}:{directory}"]
    for module in HIDDEN_IMPORTS:
        command += ["--hidden-import", module]
    command.append(str(ROOT / "main.py"))

    print(" ".join(command))
    subprocess.run(command, check=True, cwd=ROOT)
    return ROOT / "dist"


def main() -> int:
    """Parse the arguments and build."""
    parser = argparse.ArgumentParser(description="Build the macOS application bundle")
    parser.add_argument("--onefile", action="store_true", help="produce a single executable")
    parser.add_argument("--no-clean", action="store_true", help="keep previous artefacts")
    arguments = parser.parse_args()
    output = build(arguments.onefile, not arguments.no_clean)
    print(f"build finished: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
