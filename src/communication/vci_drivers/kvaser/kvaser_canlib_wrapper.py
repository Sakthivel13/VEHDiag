"""Loader and constants for the Kvaser CANlib shared library."""
from __future__ import annotations

import ctypes
from typing import Final

from ....core.exceptions import DriverNotFoundError
from ....utils.platform_utils import is_windows, load_shared_library

#: Selected canStatus return codes.
CAN_OK: Final[int] = 0
CAN_ERR_PARAM: Final[int] = -1
CAN_ERR_NOMSG: Final[int] = -2
CAN_ERR_NOTFOUND: Final[int] = -3
CAN_ERR_TIMEOUT: Final[int] = -7

STATUS_TEXT: Final[dict[int, str]] = {
    CAN_OK: "ok",
    CAN_ERR_PARAM: "invalid parameter",
    CAN_ERR_NOMSG: "no message available",
    CAN_ERR_NOTFOUND: "device not found",
    CAN_ERR_TIMEOUT: "operation timed out",
}

#: canOPEN_* flags.
CAN_OPEN_EXCLUSIVE: Final[int] = 0x0008
CAN_OPEN_ACCEPT_VIRTUAL: Final[int] = 0x0020
CAN_OPEN_CAN_FD: Final[int] = 0x0400

#: Predefined bit rate constants (canBITRATE_*).
BITRATE_CONSTANTS: Final[dict[int, int]] = {
    1_000_000: -1,
    500_000: -2,
    250_000: -3,
    125_000: -4,
    100_000: -5,
    62_000: -6,
    50_000: -7,
    83_000: -8,
    10_000: -9,
}


def load_canlib(search_paths: list[str] | None = None) -> ctypes.CDLL:
    """Load the CANlib shared library.

    Raises:
        DriverNotFoundError: CANlib is not installed on this system.
    """
    names = ("canlib32", "canlib") if is_windows() else ("canlib",)
    for name in names:
        library = load_shared_library(name, search_paths)
        if library is not None:
            library.canInitializeLibrary()
            return library
    raise DriverNotFoundError(
        "the Kvaser CANlib library could not be loaded",
        {"hint": "install the Kvaser drivers and CANlib SDK"},
    )


def describe_status(status: int) -> str:
    """Return a readable description of a CANlib status code."""
    return STATUS_TEXT.get(status, f"canStatus {status}")


def bitrate_constant(bitrate: int) -> int:
    """Return the ``canBITRATE_*`` constant closest to *bitrate*."""
    return BITRATE_CONSTANTS.get(bitrate, BITRATE_CONSTANTS[500_000])


__all__ = [
    "load_canlib",
    "describe_status",
    "bitrate_constant",
    "CAN_OPEN_EXCLUSIVE",
    "CAN_OPEN_ACCEPT_VIRTUAL",
    "CAN_OPEN_CAN_FD",
    "STATUS_TEXT",
]
