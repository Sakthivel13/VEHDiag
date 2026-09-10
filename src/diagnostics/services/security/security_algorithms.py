"""Built-in seed-key algorithms.

Real OEM algorithms are proprietary and are loaded from a DLL/SO or from a
Python script; the functions below cover the algorithms commonly used in
training material, bench setups and the bundled ECU simulator.
"""
from __future__ import annotations

from typing import Callable, Final

#: Signature of a seed-key algorithm.
SeedKeyAlgorithm = Callable[[bytes, dict[str, object]], bytes]


def xor_complement(seed: bytes, params: dict[str, object] | None = None) -> bytes:
    """Return each seed byte complemented twice (identity of ``~b ^ 0xFF``).

    Example:
        >>> xor_complement(bytes.fromhex("A3F20188")).hex().upper()
        'A3F20188'
    """
    return bytes((~b ^ 0xFF) & 0xFF for b in seed)


def bitwise_not(seed: bytes, params: dict[str, object] | None = None) -> bytes:
    """Return the one's complement of the seed.

    Example:
        >>> bitwise_not(bytes.fromhex("00FF")).hex().upper()
        'FF00'
    """
    return bytes((~b) & 0xFF for b in seed)


def add_constant(seed: bytes, params: dict[str, object] | None = None) -> bytes:
    """Add a constant to every seed byte (default ``0x42``).

    Example:
        >>> add_constant(bytes.fromhex("0102"), {"constant": 1}).hex().upper()
        '0203'
    """
    constant = int((params or {}).get("constant", 0x42))  # type: ignore[arg-type]
    return bytes((b + constant) & 0xFF for b in seed)


def xor_key(seed: bytes, params: dict[str, object] | None = None) -> bytes:
    """XOR the seed with a repeating key.

    Example:
        >>> xor_key(bytes.fromhex("A3F2"), {"key": "FF"}).hex().upper()
        '5C0D'
    """
    key_text = str((params or {}).get("key", "FF"))
    key = bytes.fromhex(key_text.replace(" ", "")) or b"\xff"
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(seed))


def rotate_left(seed: bytes, params: dict[str, object] | None = None) -> bytes:
    """Rotate the seed left by *bits* positions as one big integer.

    Example:
        >>> rotate_left(bytes.fromhex("8001"), {"bits": 1}).hex().upper()
        '0003'
    """
    bits = int((params or {}).get("bits", 1))  # type: ignore[arg-type]
    width = len(seed) * 8
    if width == 0:
        return seed
    value = int.from_bytes(seed, "big")
    bits %= width
    rotated = ((value << bits) | (value >> (width - bits))) & ((1 << width) - 1)
    return rotated.to_bytes(len(seed), "big")


def mask_and_add(seed: bytes, params: dict[str, object] | None = None) -> bytes:
    """Apply ``key = (seed & mask) + increment`` on the whole value.

    Example:
        >>> mask_and_add(bytes.fromhex("12345678"),
        ...              {"mask": 0xFFFFFFFF, "increment": 1}).hex().upper()
        '12345679'
    """
    options = params or {}
    mask = int(options.get("mask", 0xFFFFFFFF))  # type: ignore[arg-type]
    increment = int(options.get("increment", 0))  # type: ignore[arg-type]
    width = len(seed)
    value = int.from_bytes(seed, "big")
    result = ((value & mask) + increment) & ((1 << (width * 8)) - 1)
    return result.to_bytes(width, "big")


def crc_based(seed: bytes, params: dict[str, object] | None = None) -> bytes:
    """Derive the key from the CRC-16/CCITT of the seed.

    Example:
        >>> len(crc_based(bytes.fromhex("A3F20188")))
        4
    """
    from ....utils.checksum_calculator import crc16_ccitt

    crc = crc16_ccitt(seed)
    repeated = (crc.to_bytes(2, "big") * ((len(seed) // 2) + 1))[: len(seed)]
    return bytes(a ^ b for a, b in zip(seed, repeated))


#: Registry of the algorithms offered in the security access panel.
ALGORITHMS: Final[dict[str, SeedKeyAlgorithm]] = {
    "xor_complement": xor_complement,
    "bitwise_not": bitwise_not,
    "add_constant": add_constant,
    "xor_key": xor_key,
    "rotate_left": rotate_left,
    "mask_and_add": mask_and_add,
    "crc_based": crc_based,
}


def compute_key(algorithm: str, seed: bytes, params: dict[str, object] | None = None) -> bytes:
    """Compute the key for *seed* using the named *algorithm*.

    Raises:
        KeyError: The algorithm name is unknown.
    """
    key = algorithm.strip().lower()
    if key not in ALGORITHMS:
        raise KeyError(f"unknown seed-key algorithm {algorithm!r}")
    return ALGORITHMS[key](seed, params or {})


def available_algorithms() -> list[str]:
    """Return the sorted names of the built-in algorithms."""
    return sorted(ALGORITHMS)


def register_algorithm(name: str, algorithm: SeedKeyAlgorithm) -> None:
    """Register a plugin supplied algorithm under *name*."""
    ALGORITHMS[name.strip().lower()] = algorithm


__all__ = [
    "SeedKeyAlgorithm",
    "ALGORITHMS",
    "compute_key",
    "available_algorithms",
    "register_algorithm",
    "xor_complement",
    "bitwise_not",
    "add_constant",
    "xor_key",
    "rotate_left",
    "mask_and_add",
    "crc_based",
]
