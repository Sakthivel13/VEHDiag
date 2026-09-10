"""DTC code parsing and formatting."""
from __future__ import annotations

from ....core.models.dtc_model import DTC, DTCStatus

#: Category letters selected by the two most significant bits.
CATEGORY_LETTERS = {0b00: "P", 0b01: "C", 0b10: "B", 0b11: "U"}

#: DTC group boundaries used by ClearDiagnosticInformation.
GROUPS: dict[str, tuple[int, int]] = {
    "all": (0x000000, 0xFFFFFF),
    "powertrain": (0x000000, 0x3FFFFF),
    "chassis": (0x400000, 0x7FFFFF),
    "body": (0x800000, 0xBFFFFF),
    "network": (0xC00000, 0xFFFFFF),
}


def parse_dtc_bytes(raw: bytes, offset: int = 0) -> int:
    """Return the 24-bit DTC starting at *offset*.

    Raises:
        ValueError: Fewer than three bytes are available.
    """
    if len(raw) < offset + 3:
        raise ValueError("a DTC requires three bytes")
    return int.from_bytes(raw[offset : offset + 3], "big")


def format_dtc(code: int) -> str:
    """Return the plain hexadecimal five digit rendering of *code*.

    Example:
        >>> format_dtc(0xC07300)
        'C0730'
    """
    return f"{code >> 4:05X}"


def to_sae_code(code: int) -> str:
    """Return the SAE J2012 letter form of *code*.

    Example:
        >>> to_sae_code(0x010000)
        'P0100'
    """
    high = (code >> 16) & 0xFF
    middle = (code >> 8) & 0xFF
    letter = CATEGORY_LETTERS[(high >> 6) & 0b11]
    return f"{letter}{(high >> 4) & 0b11}{high & 0x0F:X}{middle >> 4:X}{middle & 0x0F:X}"


def from_sae_code(text: str) -> int:
    """Parse an SAE style code such as ``"P0100"`` into a 24-bit DTC.

    Raises:
        ValueError: The text is not a valid five character SAE code.

    Example:
        >>> hex(from_sae_code("P0100"))
        '0x10000'
    """
    candidate = text.strip().upper()
    if len(candidate) != 5:
        raise ValueError("an SAE DTC code has five characters, e.g. P0100")
    letters = {value: key for key, value in CATEGORY_LETTERS.items()}
    if candidate[0] not in letters:
        raise ValueError(f"unknown DTC category letter {candidate[0]!r}")
    try:
        digits = int(candidate[1:], 16)
    except ValueError as exc:
        raise ValueError(f"invalid DTC digits in {text!r}") from exc
    high = (letters[candidate[0]] << 6) | ((digits >> 12) & 0x0F) << 4 | ((digits >> 8) & 0x0F)
    middle = digits & 0xFF
    return (high << 16) | (middle << 8)


def group_range(name: str) -> tuple[int, int]:
    """Return the ``(first, last)`` DTC of a named group.

    Raises:
        KeyError: The group name is unknown.
    """
    key = name.strip().lower()
    if key not in GROUPS:
        raise KeyError(f"unknown DTC group {name!r}")
    return GROUPS[key]


def group_mask(name: str) -> int:
    """Return the mask value sent with ClearDiagnosticInformation."""
    if name.strip().lower() == "all":
        return 0xFFFFFF
    return group_range(name)[0]


def parse_dtc_list(payload: bytes, name_lookup: dict[int, str] | None = None) -> list[DTC]:
    """Parse a sequence of ``DTC(3) + status(1)`` records.

    Args:
        payload: Response bytes after the status availability mask.
        name_lookup: Optional mapping of DTC value to description.

    Returns:
        The decoded DTC list.

    Example:
        >>> dtcs = parse_dtc_list(bytes.fromhex("C073002F"))
        >>> dtcs[0].display_code, dtcs[0].status.confirmed
        ('C0730', True)
    """
    lookup = name_lookup or {}
    result: list[DTC] = []
    for index in range(0, len(payload) - 3, 4):
        code = int.from_bytes(payload[index : index + 3], "big")
        status = payload[index + 3]
        result.append(DTC(code=code, status=DTCStatus(status), name=lookup.get(code, "")))
    return result


def build_name_lookup(catalogue: dict[str, str] | None) -> dict[int, str]:
    """Convert a YAML catalogue keyed by hex text into an integer mapping."""
    lookup: dict[int, str] = {}
    for key, value in (catalogue or {}).items():
        try:
            lookup[int(str(key), 16)] = str(value)
        except ValueError:
            continue
    return lookup


__all__ = [
    "CATEGORY_LETTERS",
    "GROUPS",
    "parse_dtc_bytes",
    "format_dtc",
    "to_sae_code",
    "from_sae_code",
    "group_range",
    "group_mask",
    "parse_dtc_list",
    "build_name_lookup",
]
