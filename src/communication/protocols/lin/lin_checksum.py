"""LIN checksum calculation (ISO 17987 / LIN 2.x)."""
from __future__ import annotations


def classic_checksum(data: bytes) -> int:
    """Return the LIN 1.x classic checksum over the data bytes only.

    Example:
        >>> hex(classic_checksum(bytes.fromhex("0102030405060708")))
        '0xdb'
    """
    total = 0
    for byte in data:
        total += byte
        if total > 0xFF:
            total = (total & 0xFF) + 1
    return (~total) & 0xFF


def enhanced_checksum(pid: int, data: bytes) -> int:
    """Return the LIN 2.x enhanced checksum including the protected identifier.

    Example:
        >>> hex(enhanced_checksum(0x3C, bytes.fromhex("0102030405060708")))
        '0x9f'
    """
    total = pid & 0xFF
    for byte in data:
        total += byte
        if total > 0xFF:
            total = (total & 0xFF) + 1
    return (~total) & 0xFF


def protected_id(frame_id: int) -> int:
    """Return the protected identifier (PID) of a 6-bit LIN frame identifier.

    The two parity bits are computed as defined by the LIN specification.

    Example:
        >>> hex(protected_id(0x3C))
        '0x3c'
        >>> hex(protected_id(0x3D))
        '0x7d'
    """
    identifier = frame_id & 0x3F
    bit = [(identifier >> i) & 1 for i in range(6)]
    p0 = bit[0] ^ bit[1] ^ bit[2] ^ bit[4]
    p1 = (~(bit[1] ^ bit[3] ^ bit[4] ^ bit[5])) & 1
    return identifier | (p0 << 6) | (p1 << 7)


def verify_checksum(pid: int, data: bytes, checksum: int, enhanced: bool = True) -> bool:
    """Return ``True`` when *checksum* matches the computed value."""
    expected = enhanced_checksum(pid, data) if enhanced else classic_checksum(data)
    return expected == (checksum & 0xFF)


__all__ = ["classic_checksum", "enhanced_checksum", "protected_id", "verify_checksum"]
