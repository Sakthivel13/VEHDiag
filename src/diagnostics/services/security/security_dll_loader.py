"""Load OEM seed-key algorithms from a shared library or a Python script."""
from __future__ import annotations

import ctypes
import importlib.util
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from ....core.exceptions import DriverNotFoundError, FileError

_logger = logging.getLogger(__name__)

#: Entry point names tried when loading a shared library.
DEFAULT_ENTRY_POINTS: tuple[str, ...] = (
    "GenerateKeyEx",
    "GenerateKeyExOpt",
    "GenerateKey",
    "generate_key",
    "ComputeKey",
)

#: Function names tried when loading a Python script.
SCRIPT_ENTRY_POINTS: tuple[str, ...] = ("compute_key", "generate_key", "seed_to_key")


class AlgorithmSource(str, Enum):
    """Where the seed-key algorithm comes from."""

    BUILTIN = "BUILTIN"
    SHARED_LIBRARY = "SHARED_LIBRARY"
    PYTHON_SCRIPT = "PYTHON_SCRIPT"
    MANUAL = "MANUAL"


@dataclass(slots=True)
class LoadedAlgorithm:
    """A callable seed-key algorithm plus its provenance."""

    source: AlgorithmSource
    name: str
    compute: Callable[[bytes, int], bytes]
    path: Path | None = None

    def __call__(self, seed: bytes, level: int = 0x01) -> bytes:
        """Compute the key for *seed* at security *level*."""
        return self.compute(seed, level)


class SecurityDLLLoader:
    """Load an external seed-key implementation.

    The Vector/ODX convention ``GenerateKeyEx`` is supported::

        int GenerateKeyEx(const unsigned char* seed, unsigned int seedLength,
                          unsigned int securityLevel, const char* variant,
                          unsigned char* key, unsigned int maxKeyLength,
                          unsigned int* actualKeyLength);
    """

    def __init__(self, max_key_length: int = 64) -> None:
        """Create the loader."""
        self.max_key_length = max_key_length
        self.loaded: LoadedAlgorithm | None = None

    def load_library(
        self,
        path: str | Path,
        entry_point: str | None = None,
        variant: str = "",
    ) -> LoadedAlgorithm:
        """Load a DLL/SO exposing a ``GenerateKeyEx`` style function.

        Raises:
            DriverNotFoundError: The library or the entry point is missing.
        """
        library_path = Path(path).expanduser()
        if not library_path.exists():
            raise DriverNotFoundError(f"seed-key library not found: {library_path}")
        try:
            library = ctypes.CDLL(str(library_path))
        except OSError as exc:
            raise DriverNotFoundError(
                f"could not load the seed-key library {library_path}", {"cause": str(exc)}
            ) from exc

        candidates = (entry_point,) if entry_point else DEFAULT_ENTRY_POINTS
        function = None
        chosen = ""
        for name in candidates:
            if name and hasattr(library, name):
                function = getattr(library, name)
                chosen = name
                break
        if function is None:
            raise DriverNotFoundError(
                "no known seed-key entry point found in the library",
                {"tried": list(candidates), "path": str(library_path)},
            )

        function.restype = ctypes.c_int
        function.argtypes = [
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_uint,
            ctypes.c_uint,
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_uint,
            ctypes.POINTER(ctypes.c_uint),
        ]

        def compute(seed: bytes, level: int = 0x01) -> bytes:
            """Call the native entry point and return the produced key."""
            seed_buffer = (ctypes.c_ubyte * len(seed)).from_buffer_copy(seed)
            key_buffer = (ctypes.c_ubyte * self.max_key_length)()
            actual = ctypes.c_uint(0)
            status = function(
                seed_buffer,
                len(seed),
                level,
                variant.encode("ascii"),
                key_buffer,
                self.max_key_length,
                ctypes.byref(actual),
            )
            if status != 0:
                raise FileError(
                    "the seed-key library reported an error", {"status": status}
                )
            return bytes(bytearray(key_buffer)[: actual.value])

        self.loaded = LoadedAlgorithm(
            AlgorithmSource.SHARED_LIBRARY, chosen, compute, library_path
        )
        _logger.info("loaded seed-key library %s (%s)", library_path.name, chosen)
        return self.loaded

    def load_script(self, path: str | Path, function_name: str | None = None) -> LoadedAlgorithm:
        """Load a Python module exposing a ``compute_key(seed, level)`` function.

        Raises:
            FileError: The script is missing or exposes no usable function.
        """
        script_path = Path(path).expanduser()
        if not script_path.exists():
            raise FileError(f"seed-key script not found: {script_path}")
        spec = importlib.util.spec_from_file_location(f"seedkey_{script_path.stem}", script_path)
        if spec is None or spec.loader is None:
            raise FileError(f"could not import the seed-key script {script_path}")
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as exc:  # noqa: BLE001 - user supplied code
            raise FileError(
                f"the seed-key script raised during import: {exc}", {"path": str(script_path)}
            ) from exc

        candidates = (function_name,) if function_name else SCRIPT_ENTRY_POINTS
        target: Any = None
        chosen = ""
        for name in candidates:
            if name and callable(getattr(module, name, None)):
                target = getattr(module, name)
                chosen = name
                break
        if target is None:
            raise FileError(
                "the seed-key script exposes no known entry point",
                {"tried": list(candidates), "path": str(script_path)},
            )

        def compute(seed: bytes, level: int = 0x01) -> bytes:
            """Invoke the script function, tolerating a one-argument signature."""
            try:
                return bytes(target(seed, level))
            except TypeError:
                return bytes(target(seed))

        self.loaded = LoadedAlgorithm(
            AlgorithmSource.PYTHON_SCRIPT, chosen, compute, script_path
        )
        _logger.info("loaded seed-key script %s (%s)", script_path.name, chosen)
        return self.loaded

    def load(self, path: str | Path, **kwargs: Any) -> LoadedAlgorithm:
        """Load *path*, dispatching on the file suffix."""
        suffix = Path(path).suffix.lower()
        if suffix == ".py":
            return self.load_script(path, kwargs.get("function_name"))
        return self.load_library(path, kwargs.get("entry_point"), str(kwargs.get("variant", "")))


__all__ = [
    "SecurityDLLLoader",
    "LoadedAlgorithm",
    "AlgorithmSource",
    "DEFAULT_ENTRY_POINTS",
    "SCRIPT_ENTRY_POINTS",
]
