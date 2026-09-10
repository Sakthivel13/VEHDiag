"""BMW specific extensions."""
from __future__ import annotations

from typing import Any

from plugins.plugin_base import PluginBase


def bmw_seed_key(seed: bytes, params: dict[str, Any] | None = None) -> bytes:
    """Illustrative BMW style seed-key transformation.

    The real algorithms are confidential; this shows how a plugin contributes
    one to the security access panel.
    """
    from src.utils.checksum_calculator import crc16_ccitt

    crc = crc16_ccitt(seed)
    mask = (crc << 16) | crc
    value = int.from_bytes(seed, "big") if seed else 0
    key = (value ^ mask) & ((1 << (len(seed) * 8)) - 1) if seed else 0
    return key.to_bytes(max(1, len(seed)), "big")


class BMWPlugin(PluginBase):
    """Registers BMW specific DIDs and the seed-key algorithm."""

    plugin_id = "oem.bmw"
    name = "BMW"
    version = "1.0.0"
    description = "BMW specific data identifiers and seed-key algorithm"

    #: BMW specific data identifiers.
    DIDS: dict[int, dict[str, Any]] = {
        0xF150: {"name": "BMW I-Level", "format": "ASCII"},
        0xF151: {"name": "BMW vehicle order", "format": "ASCII"},
        0xF190: {"name": "VIN", "format": "ASCII", "length": 17},
        0xF1A5: {"name": "BMW coding index", "format": "HEX"},
    }

    def on_initialize(self, context: Any) -> None:
        """Register the BMW extensions."""
        count = self.register_dids(self.DIDS)
        self.register_seed_key("bmw_crc_xor", bmw_seed_key)
        self.log(f"registered {count} BMW DID(s)")

    def on_shutdown(self) -> None:
        """Nothing to release."""


__all__ = ["BMWPlugin", "bmw_seed_key"]
