"""LIN specific configuration for the connection panel."""
from __future__ import annotations

from typing import Any

#: Baudrates defined by the LIN specification.
BAUDRATES: tuple[int, ...] = (9600, 10417, 19200)


def build_options(port: str, baudrate: int = 19200, nad: int = 0x01) -> dict[str, Any]:
   """Return the LIN options for the connection profile.

   Example:
       >>> build_options("/dev/ttyUSB0")["nad"]
       1
   """
   return {
       "port": port,
       "baudrate": baudrate,
       "nad": nad,
       "enhanced_checksum": True,
       "break_bits": 13,
   }
