#!/usr/bin/env python3
"""Run the whole quality gate: linting, typing and the test suite."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Steps of the quality gate as ``(name, command, required)``.
STEPS: tuple[tuple[str, list[str], bool], ...] = (
    ("black", [sys.executable, "-m", "black", "--check", "src", "ui", "plugins", "tests"], False),
    ("isort", [sys.executable, "-m", "isort", "--check-only", "src", "ui", "plugins"], False),
    ("flake8", [sys.executable, "-m", "flake8", "src", "ui", "plugins"], False),
    ("mypy", [sys.executable, "-m", "mypy", "src"], False),
    ("pytest", [sys.executable, "-m", "pytest", "-q"], True),
)


def run(name: str, command: list[str], required: bool) -> bool:
    """Run one step and report the outcome."""
    print(f"\n=== {name} ===")
    try:
        result = subprocess.run(command, cwd=ROOT)
    except FileNotFoundError:
        print(f"{name} is not installed; skipping")
        return not required
    if result.returncode == 0:
        print(f"{name}: ok")
        return True
    print(f"{name}: failed with code {result.returncode}")
    return not required


def main() -> int:
    """Run every step and return a non-zero code when a required one failed."""
    parser = argparse.ArgumentParser(description="Run the quality gate")
    parser.add_argument("--tests-only", action="store_true", help="skip the linters")
    parser.add_argument("--coverage", action="store_true", help="produce a coverage report")
    arguments = parser.parse_args()

    steps = list(STEPS)
    if arguments.tests_only:
        steps = [step for step in steps if step[0] == "pytest"]
    if arguments.coverage:
        steps = [
            (name, command + ["--cov=src", "--cov=ui", "--cov-report=term-missing"]
             if name == "pytest" else command, required)
            for name, command, required in steps
        ]

    failures = [name for name, command, required in steps if not run(name, command, required)]
    print("\n" + "=" * 60)
    if failures:
        print(f"FAILED: {', '.join(failures)}")
        return 1
    print("every step passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
