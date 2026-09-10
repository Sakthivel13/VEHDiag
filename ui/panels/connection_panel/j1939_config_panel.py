"""J1939 specific configuration for the connection panel."""
from __future__ import annotations

from typing import Any

from src.communication.protocols.j1939.j1939_pgn import GLOBAL_ADDRESS

#: Bitrates used by J1939 networks.
BITRATES: tuple[int, ...] = (250_000, 500_000)

#: Address range reserved for diagnostic tools.
TOOL_ADDRESS_RANGE = range(128, 254)


def build_options(bitrate: int = 250_000, source_address: int = 0xF9) -> dict[str, Any]:
   """Return the J1939 options for the connection profile.

   Example:
       >>> build_options()["source_address"]
       249
   """
   return {
       "bitrate": bitrate,
       "source_address": source_address,
       "target_address": GLOBAL_ADDRESS,
   }


def is_valid_tool_address(address: int) -> bool:
   """Return ``True`` when *address* is in the tool range.

   Example:
       >>> is_valid_tool_address(0xF9)
       True
   """
   return address in TOOL_ADDRESS_RANGE
