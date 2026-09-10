"""CAN specific configuration for the connection panel."""
from __future__ import annotations

from typing import Any

#: Default identifiers for a passenger car diagnostic connection.
DEFAULTS: dict[str, Any] = {
   "bitrate": 500_000,
   "data_bitrate": 2_000_000,
   "tx_id": 0x7E0,
   "rx_id": 0x7E8,
   "functional_id": 0x7DF,
   "extended_id": False,
   "padding_enabled": True,
   "padding_byte": 0x00,
}


def build_options(**overrides: Any) -> dict[str, Any]:
   """Return the CAN options with *overrides* applied.

   Example:
       >>> build_options(bitrate=250000)["bitrate"]
       250000
   """
   options = dict(DEFAULTS)
   options.update(overrides)
   return options


def obd_identifiers(ecu_index: int = 0) -> tuple[int, int]:
   """Return the ``(request, response)`` identifiers of an OBD ECU.

   Example:
       >>> obd_identifiers(0)
       (2016, 2024)
   """
   return 0x7E0 + ecu_index, 0x7E8 + ecu_index
