#!/usr/bin/env python3
"""Create a platform specific installer from the PyInstaller output."""
from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"


def windows_installer() -> int:
    """Build the Inno Setup installer."""
    script = ROOT / "installers" / "windows" / "inno_setup.iss"
    compiler = shutil.which("iscc") or r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    if not Path(compiler).exists():
        print("Inno Setup (ISCC.exe) was not found")
        return 1
    return subprocess.run([compiler, str(script)], cwd=ROOT).returncode


def linux_packages() -> int:
    """Build the .deb package and the AppImage."""
    code = 0
    for name in ("create_deb.sh", "create_appimage.sh"):
        script = ROOT / "installers" / "linux" / name
        if not script.exists():
            continue
        script.chmod(0o755)
        code |= subprocess.run(["bash", str(script)], cwd=ROOT).returncode
    return code


def macos_dmg() -> int:
    """Build the macOS disk image."""
    script = ROOT / "installers" / "macos" / "create_dmg.sh"
    if not script.exists():
        return 1
    script.chmod(0o755)
    return subprocess.run(["bash", str(script)], cwd=ROOT).returncode


def main() -> int:
    """Dispatch on the current operating system."""
    if not DIST.exists():
        print("run the build script first: python scripts/build_<platform>.py")
        return 1
    system = platform.system()
    if system == "Windows":
        return windows_installer()
    if system == "Linux":
        return linux_packages()
    if system == "Darwin":
        return macos_dmg()
    print(f"unsupported platform: {system}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
