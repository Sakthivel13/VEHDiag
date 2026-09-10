"""Checksum and CRC helpers used by file validation and protocols."""
from __future__ import annotations

import hashlib
import zlib
from typing import Callable

_CRC16_CCITT_POLY = 0x1021
_CRC16_IBM_POLY = 0xA001


def sum8(data: bytes) -> int:
    """Return the 8-bit arithmetic sum of *data* (used by K-Line)."""
    return sum(data) & 0xFF


def twos_complement_checksum(data: bytes) -> int:
    """Return the 8-bit two's complement checksum (used by Intel HEX)."""
    return (-sum(data)) & 0xFF


def xor_checksum(data: bytes) -> int:
    """Return the 8-bit XOR of every byte."""
    result = 0
    for byte in data:
        result ^= byte
    return result


def crc8(data: bytes, poly: int = 0x1D, init: int = 0xFF, xor_out: int = 0x00) -> int:
    """Return an 8-bit CRC (default parameters match SAE J1850)."""
    crc = init
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ poly) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc ^ xor_out


def crc16_ccitt(data: bytes, init: int = 0xFFFF) -> int:
    """Return the CRC-16/CCITT-FALSE checksum of *data*."""
    crc = init
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ _CRC16_CCITT_POLY) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def crc16_modbus(data: bytes, init: int = 0xFFFF) -> int:
    """Return the CRC-16/MODBUS (IBM reflected) checksum of *data*."""
    crc = init
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ _CRC16_IBM_POLY if crc & 0x0001 else crc >> 1
    return crc & 0xFFFF


def crc32(data: bytes) -> int:
    """Return the standard CRC-32 (IEEE 802.3) of *data*."""
    return zlib.crc32(data) & 0xFFFFFFFF


def md5(data: bytes) -> str:
    """Return the hexadecimal MD5 digest of *data*."""
    return hashlib.md5(data, usedforsecurity=False).hexdigest()


def sha256(data: bytes) -> str:
    """Return the hexadecimal SHA-256 digest of *data*."""
    return hashlib.sha256(data).hexdigest()


#: Registry of the algorithms exposed in the file validator UI.
ALGORITHMS: dict[str, Callable[[bytes], int | str]] = {
    "SUM8": sum8,
    "XOR8": xor_checksum,
    "TWOS_COMPLEMENT": twos_complement_checksum,
    "CRC8": crc8,
    "CRC16_CCITT": crc16_ccitt,
    "CRC16_MODBUS": crc16_modbus,
    "CRC32": crc32,
    "MD5": md5,
    "SHA256": sha256,
}


def calculate(algorithm: str, data: bytes) -> int | str:
    """Compute *algorithm* over *data*.

    Args:
        algorithm: Key of :data:`ALGORITHMS` (case insensitive).
        data: Bytes to digest.

    Raises:
        KeyError: The algorithm is unknown.
    """
    key = algorithm.strip().upper()
    if key not in ALGORITHMS:
        raise KeyError(f"unknown checksum algorithm {algorithm!r}")
    return ALGORITHMS[key](data)


def verify(algorithm: str, data: bytes, expected: int | str) -> bool:
    """Return ``True`` when *data* digests to *expected*."""
    actual = calculate(algorithm, data)
    if isinstance(actual, str) and isinstance(expected, str):
        return actual.lower() == expected.lower().strip()
    if isinstance(expected, str):
        try:
            expected = int(expected, 16)
        except ValueError:
            return False
    return actual == expected


__all__ = [
    "sum8",
    "twos_complement_checksum",
    "xor_checksum",
    "crc8",
    "crc16_ccitt",
    "crc16_modbus",
    "crc32",
    "md5",
    "sha256",
    "ALGORITHMS",
    "calculate",
    "verify",
]
