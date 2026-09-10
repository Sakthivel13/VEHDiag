"""DoIP specific configuration for the connection panel."""
from __future__ import annotations

from typing import Any

from src.communication.protocols.ethernet.doip_routing import ACTIVATION_TYPES
from src.communication.protocols.ethernet.ethernet_config import EthernetConfig


def build_config(**overrides: Any) -> EthernetConfig:
   """Return an :class:`EthernetConfig` with *overrides* applied.

   Example:
       >>> build_config(host="10.0.0.1").host
       '10.0.0.1'
   """
   config = EthernetConfig()
   for key, value in overrides.items():
       if hasattr(config, key):
           setattr(config, key, value)
   return config


def activation_types() -> list[tuple[int, str]]:
   """Return ``(value, label)`` for every routing activation type."""
   return [(value, f"0x{value:02X} {name}") for value, name in ACTIVATION_TYPES.items()]
