"""Loader and constants for the Vector XL Driver Library.

The full XL API is large; this module provides library discovery, the status
code table and the handful of structures the platform needs when python-can is
unavailable.
"""
from __future__ import annotations

import ctypes
from typing import Final

from ....core.exceptions import DriverNotFoundError
from ....utils.platform_utils import is_windows, load_shared_library

#: Bus type constants of the XL API.
XL_BUS_TYPE_CAN: Final[int] = 0x00000001
XL_BUS_TYPE_LIN: Final[int] = 0x00000002
XL_BUS_TYPE_FLEXRAY: Final[int] = 0x00000004
XL_BUS_TYPE_ETHERNET: Final[int] = 0x00000010

#: Selected XL status codes.
XL_SUCCESS: Final[int] = 0
XL_ERR_QUEUE_IS_EMPTY: Final[int] = 10
XL_ERR_QUEUE_IS_FULL: Final[int] = 11
XL_ERR_HW_NOT_PRESENT: Final[int] = 129
XL_ERR_INVALID_ACCESS: Final[int] = 118

STATUS_TEXT: Final[dict[int, str]] = {
    XL_SUCCESS: "ok",
    XL_ERR_QUEUE_IS_EMPTY: "receive queue empty",
    XL_ERR_QUEUE_IS_FULL: "transmit queue full",
    XL_ERR_HW_NOT_PRESENT: "hardware not present",
    XL_ERR_INVALID_ACCESS: "invalid channel access",
}


class XLcanTxEvent(ctypes.Structure):
    """Reduced XL CAN transmit event structure."""

    _fields_ = [
        ("tag", ctypes.c_uint16),
        ("transId", ctypes.c_uint16),
        ("channelIndex", ctypes.c_ubyte),
        ("reserved", ctypes.c_ubyte * 3),
        ("canId", ctypes.c_uint32),
        ("msgFlags", ctypes.c_uint32),
        ("dlc", ctypes.c_ubyte),
        ("reserved1", ctypes.c_ubyte * 7),
        ("data", ctypes.c_ubyte * 64),
    ]


def load_xl_library(search_paths: list[str] | None = None) -> ctypes.CDLL:
    """Load ``vxlapi64``/``vxlapi``.

    Raises:
        DriverNotFoundError: The Vector driver library is not installed.
    """
    for name in ("vxlapi64", "vxlapi", "libvxlapi"):
        library = load_shared_library(name, search_paths)
        if library is not None:
            return library
    raise DriverNotFoundError(
        "the Vector XL Driver Library could not be loaded",
        {"hint": "install the Vector Driver Setup", "windows": is_windows()},
    )


def describe_status(status: int) -> str:
    """Return a readable description of an XL status code."""
    return STATUS_TEXT.get(status, f"XL status {status}")


def channel_mask(channel_index: int) -> int:
    """Return the XL channel mask for a zero based channel index."""
    return 1 << channel_index


__all__ = [
    "XL_BUS_TYPE_CAN",
    "XL_BUS_TYPE_LIN",
    "XL_BUS_TYPE_FLEXRAY",
    "XL_BUS_TYPE_ETHERNET",
    "XLcanTxEvent",
    "load_xl_library",
    "describe_status",
    "channel_mask",
]
