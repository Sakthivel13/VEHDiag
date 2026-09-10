"""Volkswagen group specific extensions."""
from __future__ import annotations

from typing import Any

from plugins.plugin_base import PluginBase


def vw_seed_key(seed: bytes, params: dict[str, Any] | None = None) -> bytes:
    """Illustrative VAG style seed-key transformation.

    Real algorithms are confidential; this demonstrates the plugin API and is
    only compatible with the bundled simulator when configured accordingly.
    """
    constant = int((params or {}).get("constant", 0x3F))
    value = int.from_bytes(seed, "big") if seed else 0
    key = ((value << 3) | (value >> max(1, len(seed) * 8 - 3))) ^ (constant * 0x01010101)
    return (key & ((1 << (len(seed) * 8)) - 1)).to_bytes(max(1, len(seed)), "big")


class VolkswagenPlugin(PluginBase):
    """Registers VAG specific DIDs, routines and the seed-key algorithm."""

    plugin_id = "oem.volkswagen"
    name = "Volkswagen group"
    version = "1.0.0"
    description = "VAG specific data identifiers and seed-key algorithm"

    #: VAG specific data identifiers.
    DIDS: dict[int, dict[str, Any]] = {
        0xF187: {"name": "VAG spare part number", "format": "ASCII"},
        0xF189: {"name": "VAG software version", "format": "ASCII"},
        0xF19E: {"name": "VAG ODX file identifier", "format": "ASCII"},
        0x0405: {"name": "VAG coding value", "format": "HEX"},
        0x0600: {"name": "VAG adaptation channel", "format": "HEX"},
    }

    #: Routines commonly used on VAG control units.
    ROUTINES: dict[int, str] = {
        0x0203: "Check programming preconditions",
        0x0301: "Reset adaptation values",
    }

    def on_initialize(self, context: Any) -> None:
        """Register the VAG extensions."""
        count = self.register_dids(self.DIDS)
        self.register_seed_key("vag_shift_xor", vw_seed_key)
        self.log(f"registered {count} VAG DID(s) and {len(self.ROUTINES)} routine(s)")

    def on_shutdown(self) -> None:
        """Nothing to release."""


__all__ = ["VolkswagenPlugin", "vw_seed_key"]
