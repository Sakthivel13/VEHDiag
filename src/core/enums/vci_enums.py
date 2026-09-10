"""Vehicle Communication Interface (VCI) enumerations."""
from __future__ import annotations

from enum import Enum


class VCIType(str, Enum):
    """Supported VCI hardware families."""

    PCAN = "PCAN"
    PCAN_FD = "PCAN_FD"
    VECTOR = "VECTOR"
    KVASER_BLACKBIRD_V2 = "KVASER_BLACKBIRD_V2"
    KVASER_LEAF_V3 = "KVASER_LEAF_V3"
    INTREPIDCS = "INTREPIDCS"
    SOCKETCAN = "SOCKETCAN"
    SERIAL = "SERIAL"
    DOIP_ETHERNET = "DOIP_ETHERNET"
    VIRTUAL = "VIRTUAL"

    @property
    def display_name(self) -> str:
        """Return the human readable vendor/product name."""
        return {
            VCIType.PCAN: "PEAK PCAN-USB",
            VCIType.PCAN_FD: "PEAK PCAN-USB FD",
            VCIType.VECTOR: "Vector (XL Driver Library)",
            VCIType.KVASER_BLACKBIRD_V2: "Kvaser BlackBird V2",
            VCIType.KVASER_LEAF_V3: "Kvaser Leaf V3",
            VCIType.INTREPIDCS: "Intrepid Control Systems neoVI",
            VCIType.SOCKETCAN: "Linux SocketCAN",
            VCIType.SERIAL: "Serial / K-Line adapter",
            VCIType.DOIP_ETHERNET: "Ethernet (DoIP)",
            VCIType.VIRTUAL: "Virtual VCI (simulation)",
        }[self]

    @property
    def requires_vendor_library(self) -> bool:
        """Return ``True`` when a proprietary shared library must be present."""
        return self in (
            VCIType.PCAN,
            VCIType.PCAN_FD,
            VCIType.VECTOR,
            VCIType.KVASER_BLACKBIRD_V2,
            VCIType.KVASER_LEAF_V3,
            VCIType.INTREPIDCS,
        )


class VCIState(str, Enum):
    """Lifecycle state of a VCI driver instance."""

    UNINITIALIZED = "UNINITIALIZED"
    INITIALIZED = "INITIALIZED"
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    ERROR = "ERROR"


class VCICapability(str, Enum):
    """Optional features a VCI may advertise."""

    CAN = "CAN"
    CAN_FD = "CAN_FD"
    LIN = "LIN"
    FLEXRAY = "FLEXRAY"
    KLINE = "KLINE"
    ETHERNET = "ETHERNET"
    LISTEN_ONLY = "LISTEN_ONLY"
    HARDWARE_TIMESTAMPS = "HARDWARE_TIMESTAMPS"
    BUS_STATISTICS = "BUS_STATISTICS"
    ERROR_FRAMES = "ERROR_FRAMES"


__all__ = ["VCIType", "VCIState", "VCICapability"]
