"""Compatibility shim.

All project metadata lives in :file:`pyproject.toml`; this file exists so that
legacy tooling (``python setup.py ...``) keeps working.
"""

from setuptools import setup

if __name__ == "__main__":
    setup()
