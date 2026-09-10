"""Template for an OEM specific plugin - copy and adapt."""
from __future__ import annotations

from typing import Any

from plugins.plugin_base import PluginBase


def oem_seed_key(seed: bytes, params: dict[str, Any] | None = None) -> bytes:
    """Example OEM seed-key algorithm.

    Args:
        seed: The seed returned by the ECU.
        params: Optional parameters from the configuration.

    Returns:
        The key to send back.
    """
    constant = int((params or {}).get("constant", 0x5A))
    return bytes(((b << 1) & 0xFF) ^ constant for b in seed)


class TemplateOEMPlugin(PluginBase):
    """Skeleton plugin registering OEM DIDs and a seed-key algorithm."""

    plugin_id = "oem.template"
    name = "Template OEM"
    version = "1.0.0"
    description = "Starting point for an OEM specific extension"

    #: DIDs contributed by this OEM.
    DIDS: dict[int, dict[str, Any]] = {
        0xF1F0: {"name": "OEM calibration identifier", "format": "ASCII"},
        0xF1F1: {"name": "OEM production date", "format": "BCD", "length": 4},
    }

    def on_initialize(self, context: Any) -> None:
        """Register the OEM specific extensions."""
        count = self.register_dids(self.DIDS)
        self.register_seed_key("oem_template", oem_seed_key)
        self.log(f"registered {count} DID(s) and the seed-key algorithm 'oem_template'")

    def on_shutdown(self) -> None:
        """Nothing to release."""
        self.log("shutting down")


__all__ = ["TemplateOEMPlugin", "oem_seed_key"]
