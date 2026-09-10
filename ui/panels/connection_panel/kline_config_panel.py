"""K-Line specific configuration for the connection panel."""
from __future__ import annotations

from typing import Any

from src.communication.protocols.kline.kline_timing import KLineTiming
from src.core.enums.protocol_enums import KLineInitType

#: Initialisation strategies offered in the UI.
INIT_TYPES: tuple[tuple[str, str], ...] = (
   (KLineInitType.FAST_INIT.value, "Fast init (ISO 14230)"),
   (KLineInitType.FIVE_BAUD.value, "5 baud init (ISO 9141)"),
   (KLineInitType.NONE.value, "No initialisation"),
)


def build_options(port: str, baudrate: int = 10400, init: str = "FAST_INIT") -> dict[str, Any]:
   """Return the K-Line options for the connection profile.

   Example:
       >>> build_options("/dev/ttyUSB0")["baudrate"]
       10400
   """
   timing = (
       KLineTiming.kwp2000_fast() if init == KLineInitType.FAST_INIT.value
       else KLineTiming.iso9141()
   )
   return {
       "port": port,
       "baudrate": baudrate,
       "init_type": init,
       "p1_ms": timing.p1_ms,
       "p2_ms": timing.p2_ms,
       "p3_ms": timing.p3_ms,
       "p4_ms": timing.p4_ms,
   }
