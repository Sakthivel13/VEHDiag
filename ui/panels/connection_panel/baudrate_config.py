"""Baudrate and bit timing helpers for the connection panel."""
from __future__ import annotations

from src.communication.protocols.can.can_timing import (
   FD_DATA_BITRATES,
   STANDARD_BITRATES,
   BitTiming,
   bus_load_percent,
   calculate_bit_timing,
)

#: Baudrates offered for serial K-Line and LIN adapters.
SERIAL_BAUDRATES: tuple[int, ...] = (9600, 10400, 19200, 38400, 57600, 115200)


def can_bitrates() -> list[tuple[int, str]]:
   """Return ``(value, label)`` for every standard CAN bitrate.

   Example:
       >>> (500000, "500 kbit/s") in can_bitrates()
       True
   """
   return [(rate, f"{rate // 1000} kbit/s") for rate in STANDARD_BITRATES]


def fd_data_bitrates() -> list[tuple[int, str]]:
   """Return ``(value, label)`` for every CAN FD data phase bitrate."""
   return [(rate, f"{rate // 1000} kbit/s") for rate in FD_DATA_BITRATES]


def serial_baudrates() -> list[tuple[int, str]]:
   """Return ``(value, label)`` for the serial baudrates."""
   return [(rate, f"{rate} baud") for rate in SERIAL_BAUDRATES]


def timing_for(bitrate: int, clock_hz: int = 80_000_000) -> BitTiming:
   """Return the bit timing registers for *bitrate*."""
   return calculate_bit_timing(bitrate, clock_hz)


def estimated_bus_load(bitrate: int, frames_per_second: float) -> float:
   """Return the estimated bus load in percent."""
   return bus_load_percent(bitrate, frames_per_second)
