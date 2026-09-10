"""Communication message model shared by all protocol layers."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from ..enums.protocol_enums import MessageDirection, ProtocolType


@dataclass(slots=True)
class BusMessage:
    """A single raw frame exchanged on a vehicle bus.

    Attributes:
        data: Payload bytes of the frame (without the bus level framing).
        arbitration_id: CAN/J1939 identifier, LIN PID, or DoIP target address.
        direction: Whether the frame was transmitted or received.
        protocol: Protocol the frame belongs to.
        timestamp: Unix timestamp with sub-microsecond resolution.
        channel: Hardware channel name the frame was seen on.
        is_extended_id: ``True`` for 29-bit CAN identifiers.
        is_fd: ``True`` for CAN FD frames.
        bitrate_switch: ``True`` when the FD data phase used the higher bitrate.
        is_error_frame: ``True`` for bus error frames.
        metadata: Free-form extra information supplied by the driver.
    """

    data: bytes = b""
    arbitration_id: int = 0
    direction: MessageDirection = MessageDirection.TX
    protocol: ProtocolType = ProtocolType.CAN
    timestamp: float = field(default_factory=time.time)
    channel: str = ""
    is_extended_id: bool = False
    is_fd: bool = False
    bitrate_switch: bool = False
    is_error_frame: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def dlc(self) -> int:
        """Return the payload length in bytes."""
        return len(self.data)

    @property
    def hex_data(self) -> str:
        """Return the payload as space separated uppercase hex."""
        return " ".join(f"{b:02X}" for b in self.data)

    @property
    def id_text(self) -> str:
        """Return the identifier formatted for display."""
        width = 8 if self.is_extended_id else 3
        return f"0x{self.arbitration_id:0{width}X}"

    def __str__(self) -> str:  # noqa: D105 - trivial
        return f"[{self.direction.value}] {self.id_text} [{self.dlc}] {self.hex_data}"


@dataclass(slots=True)
class DiagnosticMessage:
    """An assembled diagnostic (UDS) message above the transport layer.

    Attributes:
        payload: Complete UDS payload starting with the service identifier.
        direction: Request (TX) or response (RX).
        timestamp: Unix timestamp at assembly time.
        source_address: Logical source address (DoIP) or 0.
        target_address: Logical target address (DoIP) or 0.
        is_functional: ``True`` for functionally addressed requests.
    """

    payload: bytes = b""
    direction: MessageDirection = MessageDirection.TX
    timestamp: float = field(default_factory=time.time)
    source_address: int = 0
    target_address: int = 0
    is_functional: bool = False

    @property
    def service_id(self) -> int | None:
        """Return the first payload byte, or ``None`` for an empty payload."""
        return self.payload[0] if self.payload else None

    @property
    def hex_payload(self) -> str:
        """Return the payload as space separated uppercase hex."""
        return " ".join(f"{b:02X}" for b in self.payload)

    def __len__(self) -> int:  # noqa: D105 - trivial
        return len(self.payload)


__all__ = ["BusMessage", "DiagnosticMessage"]
