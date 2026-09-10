"""Protocol selection helpers."""
from __future__ import annotations

from src.core.enums.protocol_enums import ProtocolType

#: Protocols offered in the connection panel, in display order.
SELECTABLE: tuple[ProtocolType, ...] = (
   ProtocolType.CAN,
   ProtocolType.CAN_FD,
   ProtocolType.DOIP,
   ProtocolType.KLINE,
   ProtocolType.LIN,
   ProtocolType.J1939,
   ProtocolType.FLEXRAY,
)

#: Index of the configuration page each protocol uses.
PAGE_INDEX: dict[ProtocolType, int] = {
   ProtocolType.CAN: 0,
   ProtocolType.CAN_FD: 0,
   ProtocolType.FLEXRAY: 0,
   ProtocolType.DOIP: 1,
   ProtocolType.ETHERNET: 1,
   ProtocolType.KLINE: 2,
   ProtocolType.LIN: 2,
   ProtocolType.J1939: 3,
}


def selectable_protocols() -> list[tuple[str, str]]:
   """Return ``(value, label)`` for every selectable protocol.

   Example:
       >>> ("CAN", "CAN (ISO 11898)") in selectable_protocols()
       True
   """
   return [(protocol.value, protocol.display_name) for protocol in SELECTABLE]


def page_for(protocol: ProtocolType) -> int:
   """Return the configuration page index used by *protocol*."""
   return PAGE_INDEX.get(protocol, 0)
