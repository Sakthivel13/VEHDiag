"""Minimal ctypes wrapper around the PEAK PCANBasic shared library.

Only the subset needed by the platform is bound. When the library cannot be
loaded, :class:`PCANBasicWrapper` raises :class:`DriverNotFoundError` so the
factory can fall back to python-can or to the virtual driver.
"""
from __future__ import annotations

import ctypes
import logging
from typing import Final

from ....core.exceptions import DriverNotFoundError, VCIError
from ....utils.platform_utils import is_windows, load_shared_library

_logger = logging.getLogger(__name__)

#: PCAN channel handles for the USB devices.
PCAN_USBBUS: Final[dict[int, int]] = {index: 0x50 + index for index in range(1, 17)}

#: Bit timing codes for the classic controller (SJA1000 style).
PCAN_BAUD_CODES: Final[dict[int, int]] = {
    1_000_000: 0x0014,
    800_000: 0x0016,
    500_000: 0x001C,
    250_000: 0x011C,
    125_000: 0x031C,
    100_000: 0x432F,
    50_000: 0x472F,
    20_000: 0x532F,
    10_000: 0x672F,
}

#: Selected PCAN status codes.
PCAN_ERROR_OK: Final[int] = 0x00000
PCAN_ERROR_XMTFULL: Final[int] = 0x00001
PCAN_ERROR_BUSLIGHT: Final[int] = 0x00002
PCAN_ERROR_BUSHEAVY: Final[int] = 0x00004
PCAN_ERROR_BUSOFF: Final[int] = 0x00008
PCAN_ERROR_QRCVEMPTY: Final[int] = 0x00020
PCAN_ERROR_ILLHW: Final[int] = 0x01400

STATUS_TEXT: Final[dict[int, str]] = {
    PCAN_ERROR_OK: "ok",
    PCAN_ERROR_XMTFULL: "transmit buffer full",
    PCAN_ERROR_BUSLIGHT: "bus error: light",
    PCAN_ERROR_BUSHEAVY: "bus error: heavy",
    PCAN_ERROR_BUSOFF: "bus off",
    PCAN_ERROR_QRCVEMPTY: "receive queue empty",
    PCAN_ERROR_ILLHW: "illegal hardware handle",
}


class TPCANMsg(ctypes.Structure):
    """Native PCAN message structure."""

    _fields_ = [
        ("ID", ctypes.c_uint32),
        ("MSGTYPE", ctypes.c_ubyte),
        ("LEN", ctypes.c_ubyte),
        ("DATA", ctypes.c_ubyte * 8),
    ]


class TPCANTimestamp(ctypes.Structure):
    """Native PCAN timestamp structure."""

    _fields_ = [
        ("millis", ctypes.c_uint32),
        ("millis_overflow", ctypes.c_uint16),
        ("micros", ctypes.c_uint16),
    ]


class PCANBasicWrapper:
    """Thin binding of the PCANBasic entry points used by the platform.

    Raises:
        DriverNotFoundError: The shared library is not installed.
    """

    def __init__(self, search_paths: list[str] | None = None) -> None:
        """Load the shared library."""
        name = "PCANBasic" if is_windows() else "pcanbasic"
        self._lib = load_shared_library(name, search_paths)
        if self._lib is None:
            raise DriverNotFoundError(
                "the PCANBasic library could not be loaded",
                {"hint": "install the PEAK driver package for your platform"},
            )
        self._bind()

    def _bind(self) -> None:
        """Declare the argument and return types of the bound functions."""
        self._lib.CAN_Initialize.restype = ctypes.c_uint32
        self._lib.CAN_Initialize.argtypes = [
            ctypes.c_uint16,
            ctypes.c_uint16,
            ctypes.c_ubyte,
            ctypes.c_uint32,
            ctypes.c_uint16,
        ]
        self._lib.CAN_Uninitialize.restype = ctypes.c_uint32
        self._lib.CAN_Uninitialize.argtypes = [ctypes.c_uint16]
        self._lib.CAN_Write.restype = ctypes.c_uint32
        self._lib.CAN_Write.argtypes = [ctypes.c_uint16, ctypes.POINTER(TPCANMsg)]
        self._lib.CAN_Read.restype = ctypes.c_uint32
        self._lib.CAN_Read.argtypes = [
            ctypes.c_uint16,
            ctypes.POINTER(TPCANMsg),
            ctypes.POINTER(TPCANTimestamp),
        ]
        self._lib.CAN_Reset.restype = ctypes.c_uint32
        self._lib.CAN_Reset.argtypes = [ctypes.c_uint16]
        self._lib.CAN_GetStatus.restype = ctypes.c_uint32
        self._lib.CAN_GetStatus.argtypes = [ctypes.c_uint16]

    @staticmethod
    def describe(status: int) -> str:
        """Return a readable description of a PCAN status code."""
        return STATUS_TEXT.get(status, f"PCAN status 0x{status:05X}")

    def _check(self, status: int, action: str) -> None:
        """Raise when *status* indicates an error.

        Raises:
            VCIError: The operation failed.
        """
        if status not in (PCAN_ERROR_OK, PCAN_ERROR_QRCVEMPTY):
            raise VCIError(f"{action} failed: {self.describe(status)}", {"status": status})

    def initialize(self, channel: int, bitrate: int) -> None:
        """Open *channel* at *bitrate* bit/s."""
        code = PCAN_BAUD_CODES.get(bitrate, PCAN_BAUD_CODES[500_000])
        status = self._lib.CAN_Initialize(channel, code, 0, 0, 0)
        self._check(status, "CAN_Initialize")

    def uninitialize(self, channel: int) -> None:
        """Close *channel*."""
        self._lib.CAN_Uninitialize(channel)

    def reset(self, channel: int) -> None:
        """Reset the controller of *channel* (bus-off recovery)."""
        self._check(self._lib.CAN_Reset(channel), "CAN_Reset")

    def status(self, channel: int) -> int:
        """Return the raw status code of *channel*."""
        return int(self._lib.CAN_GetStatus(channel))

    def write(self, channel: int, can_id: int, data: bytes, extended: bool = False) -> None:
        """Transmit one classic CAN frame."""
        message = TPCANMsg()
        message.ID = can_id
        message.MSGTYPE = 0x02 if extended else 0x00
        message.LEN = min(8, len(data))
        for index in range(message.LEN):
            message.DATA[index] = data[index]
        self._check(self._lib.CAN_Write(channel, ctypes.byref(message)), "CAN_Write")

    def read(self, channel: int) -> tuple[int, bytes, bool] | None:
        """Read one frame, returning ``(id, data, extended)`` or ``None``."""
        message = TPCANMsg()
        timestamp = TPCANTimestamp()
        status = self._lib.CAN_Read(channel, ctypes.byref(message), ctypes.byref(timestamp))
        if status == PCAN_ERROR_QRCVEMPTY:
            return None
        self._check(status, "CAN_Read")
        data = bytes(bytearray(message.DATA)[: message.LEN])
        return int(message.ID), data, bool(message.MSGTYPE & 0x02)


__all__ = [
    "PCANBasicWrapper",
    "PCAN_USBBUS",
    "PCAN_BAUD_CODES",
    "STATUS_TEXT",
    "TPCANMsg",
    "TPCANTimestamp",
]
