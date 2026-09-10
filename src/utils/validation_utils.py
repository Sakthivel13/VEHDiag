"""Input validation helpers shared by the UI and the service layer."""
from __future__ import annotations

import ipaddress
import re
from pathlib import Path

from .byte_utils import clean_hex, hex_to_bytes

_VIN_RE = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")


def validate_hex_string(text: str, min_bytes: int = 0, max_bytes: int | None = None) -> bytes:
    """Parse and length-check a hex string.

    Args:
        text: The hex text entered by the user.
        min_bytes: Minimum acceptable length in bytes.
        max_bytes: Maximum acceptable length, or ``None`` for unlimited.

    Returns:
        The parsed bytes.

    Raises:
        ValueError: The text is not hex or violates the length bounds.
    """
    cleaned = clean_hex(text)
    if len(cleaned) != len(text.replace(" ", "").replace("0x", "").replace(":", "").replace("-", "")):
        raise ValueError("the value contains non-hexadecimal characters")
    data = hex_to_bytes(text)
    if len(data) < min_bytes:
        raise ValueError(f"at least {min_bytes} byte(s) required, got {len(data)}")
    if max_bytes is not None and len(data) > max_bytes:
        raise ValueError(f"at most {max_bytes} byte(s) allowed, got {len(data)}")
    return data


def validate_did(value: str | int) -> int:
    """Validate and normalise a 16-bit data identifier.

    Raises:
        ValueError: The identifier is malformed or out of range.
    """
    did = int(clean_hex(value), 16) if isinstance(value, str) else int(value)
    if not 0x0000 <= did <= 0xFFFF:
        raise ValueError(f"data identifier 0x{did:X} is outside 0x0000..0xFFFF")
    return did


def validate_dtc(value: str | int) -> int:
    """Validate and normalise a 24-bit DTC value.

    Raises:
        ValueError: The DTC is malformed or out of range.
    """
    dtc = int(clean_hex(value), 16) if isinstance(value, str) else int(value)
    if not 0x000000 <= dtc <= 0xFFFFFF:
        raise ValueError(f"DTC 0x{dtc:X} is outside 0x000000..0xFFFFFF")
    return dtc


def validate_can_id(value: str | int, extended: bool = False) -> int:
    """Validate a CAN identifier for the 11-bit or 29-bit range.

    Raises:
        ValueError: The identifier is out of range.
    """
    can_id = int(clean_hex(value), 16) if isinstance(value, str) else int(value)
    limit = 0x1FFFFFFF if extended else 0x7FF
    if not 0 <= can_id <= limit:
        kind = "29-bit" if extended else "11-bit"
        raise ValueError(f"CAN identifier 0x{can_id:X} exceeds the {kind} range")
    return can_id


def validate_bitrate(value: int) -> int:
    """Validate a CAN bitrate in bit/s.

    Raises:
        ValueError: The bitrate is outside 5 kbit/s .. 8 Mbit/s.
    """
    if not 5_000 <= value <= 8_000_000:
        raise ValueError(f"bitrate {value} bit/s is outside the supported range")
    return value


def validate_ip_address(text: str) -> str:
    """Validate an IPv4/IPv6 address.

    Raises:
        ValueError: The address is malformed.
    """
    return str(ipaddress.ip_address(text.strip()))


def validate_port(value: int) -> int:
    """Validate a TCP/UDP port number.

    Raises:
        ValueError: The port is outside 1..65535.
    """
    if not 1 <= int(value) <= 65535:
        raise ValueError(f"port {value} is outside 1..65535")
    return int(value)


def validate_vin(text: str) -> str:
    """Validate a 17 character Vehicle Identification Number.

    Raises:
        ValueError: The VIN has the wrong length or forbidden characters.
    """
    candidate = text.strip().upper()
    if not _VIN_RE.match(candidate):
        raise ValueError("a VIN must be 17 characters and may not contain I, O or Q")
    return candidate


def validate_file_exists(path: str | Path, suffixes: tuple[str, ...] | None = None) -> Path:
    """Validate that *path* exists and optionally has an accepted suffix.

    Raises:
        ValueError: The file is missing, is a directory or has a bad suffix.
    """
    candidate = Path(path).expanduser()
    if not candidate.exists():
        raise ValueError(f"file not found: {candidate}")
    if not candidate.is_file():
        raise ValueError(f"not a regular file: {candidate}")
    if suffixes and candidate.suffix.lower() not in suffixes:
        raise ValueError(f"unsupported file type {candidate.suffix!r}, expected one of {suffixes}")
    return candidate


def validate_range(value: float, minimum: float, maximum: float, name: str = "value") -> float:
    """Validate that *minimum* <= *value* <= *maximum*.

    Raises:
        ValueError: The value is out of range.
    """
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} {value} is outside {minimum}..{maximum}")
    return value


def validate_uds_request(payload: bytes) -> bytes:
    """Perform basic sanity checks on a raw UDS request.

    Raises:
        ValueError: The payload is empty or uses a reserved service identifier.
    """
    if not payload:
        raise ValueError("a UDS request must contain at least the service identifier")
    if payload[0] in (0x7F,):
        raise ValueError("0x7F is reserved for negative responses and cannot be requested")
    return payload


__all__ = [
    "validate_hex_string",
    "validate_did",
    "validate_dtc",
    "validate_can_id",
    "validate_bitrate",
    "validate_ip_address",
    "validate_port",
    "validate_vin",
    "validate_file_exists",
    "validate_range",
    "validate_uds_request",
]
