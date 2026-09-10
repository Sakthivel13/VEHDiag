"""Protocol related enumerations."""
from __future__ import annotations

from enum import Enum, IntEnum


class ProtocolType(str, Enum):
    """Supported vehicle bus / diagnostic protocols."""

    CAN = "CAN"
    CAN_FD = "CAN_FD"
    KLINE = "KLINE"
    LIN = "LIN"
    FLEXRAY = "FLEXRAY"
    ETHERNET = "ETHERNET"
    DOIP = "DOIP"
    J1939 = "J1939"
    VIRTUAL = "VIRTUAL"

    @property
    def display_name(self) -> str:
        """Return the label shown in the user interface."""
        return {
            ProtocolType.CAN: "CAN (ISO 11898)",
            ProtocolType.CAN_FD: "CAN FD",
            ProtocolType.KLINE: "K-Line (ISO 9141 / 14230)",
            ProtocolType.LIN: "LIN",
            ProtocolType.FLEXRAY: "FlexRay",
            ProtocolType.ETHERNET: "Automotive Ethernet",
            ProtocolType.DOIP: "DoIP (ISO 13400)",
            ProtocolType.J1939: "SAE J1939",
            ProtocolType.VIRTUAL: "Virtual bus",
        }[self]

    @property
    def is_can_based(self) -> bool:
        """Return ``True`` for protocols carried over a CAN physical layer."""
        return self in (ProtocolType.CAN, ProtocolType.CAN_FD, ProtocolType.J1939)


class ConnectionState(str, Enum):
    """State machine values for a transport / connection."""

    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    DISCONNECTING = "DISCONNECTING"
    ERROR = "ERROR"


class AddressingMode(str, Enum):
    """UDS addressing mode."""

    PHYSICAL = "PHYSICAL"
    FUNCTIONAL = "FUNCTIONAL"


class IsoTpAddressingFormat(str, Enum):
    """ISO 15765-2 addressing formats."""

    NORMAL_11BIT = "NORMAL_11BIT"
    NORMAL_29BIT = "NORMAL_29BIT"
    EXTENDED_11BIT = "EXTENDED_11BIT"
    EXTENDED_29BIT = "EXTENDED_29BIT"
    MIXED_11BIT = "MIXED_11BIT"
    MIXED_29BIT = "MIXED_29BIT"


class IsoTpFrameType(IntEnum):
    """ISO-TP PCI frame types (upper nibble of the first PCI byte)."""

    SINGLE_FRAME = 0x0
    FIRST_FRAME = 0x1
    CONSECUTIVE_FRAME = 0x2
    FLOW_CONTROL = 0x3


class FlowStatus(IntEnum):
    """ISO-TP flow control status values."""

    CONTINUE_TO_SEND = 0x0
    WAIT = 0x1
    OVERFLOW = 0x2


class MessageDirection(str, Enum):
    """Direction of a logged bus message."""

    TX = "TX"
    RX = "RX"


class KLineInitType(str, Enum):
    """K-Line initialisation strategies."""

    FIVE_BAUD = "FIVE_BAUD"
    FAST_INIT = "FAST_INIT"
    NONE = "NONE"


__all__ = [
    "ProtocolType",
    "ConnectionState",
    "AddressingMode",
    "IsoTpAddressingFormat",
    "IsoTpFrameType",
    "FlowStatus",
    "MessageDirection",
    "KLineInitType",
]
