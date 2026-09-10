"""CAN message helpers built on top of the shared :class:`BusMessage`."""
from __future__ import annotations

from dataclasses import dataclass

from ....core.enums.protocol_enums import MessageDirection, ProtocolType
from ....core.models.message_model import BusMessage

#: Mapping of CAN FD data length codes to payload byte counts.
DLC_TO_LENGTH: dict[int, int] = {
    **{i: i for i in range(9)},
    9: 12,
    10: 16,
    11: 20,
    12: 24,
    13: 32,
    14: 48,
    15: 64,
}

#: Reverse mapping used when encoding an FD frame.
LENGTH_TO_DLC: dict[int, int] = {length: dlc for dlc, length in sorted(DLC_TO_LENGTH.items())}


def length_to_dlc(length: int) -> int:
    """Return the DLC encoding the smallest FD frame holding *length* bytes.

    Example:
        >>> length_to_dlc(8)
        8
        >>> length_to_dlc(20)
        11
    """
    for candidate in sorted(LENGTH_TO_DLC):
        if length <= candidate:
            return LENGTH_TO_DLC[candidate]
    return 15


def dlc_to_length(dlc: int) -> int:
    """Return the payload length encoded by *dlc*."""
    return DLC_TO_LENGTH.get(dlc & 0x0F, 0)


@dataclass(slots=True)
class CANFrame:
    """A convenience wrapper around a single CAN or CAN FD frame."""

    arbitration_id: int
    data: bytes = b""
    is_extended_id: bool = False
    is_fd: bool = False
    bitrate_switch: bool = False
    is_remote_frame: bool = False
    is_error_frame: bool = False
    channel: str = ""
    timestamp: float = 0.0

    @property
    def dlc(self) -> int:
        """Return the data length code of the frame."""
        return length_to_dlc(len(self.data)) if self.is_fd else min(8, len(self.data))

    def to_bus_message(self, direction: MessageDirection = MessageDirection.TX) -> BusMessage:
        """Convert the frame into the generic :class:`BusMessage` model."""
        return BusMessage(
            data=self.data,
            arbitration_id=self.arbitration_id,
            direction=direction,
            protocol=ProtocolType.CAN_FD if self.is_fd else ProtocolType.CAN,
            channel=self.channel,
            is_extended_id=self.is_extended_id,
            is_fd=self.is_fd,
            bitrate_switch=self.bitrate_switch,
            is_error_frame=self.is_error_frame,
            timestamp=self.timestamp or 0.0,
        )

    @classmethod
    def from_bus_message(cls, message: BusMessage) -> "CANFrame":
        """Build a frame from a generic :class:`BusMessage`."""
        return cls(
            arbitration_id=message.arbitration_id,
            data=message.data,
            is_extended_id=message.is_extended_id,
            is_fd=message.is_fd,
            bitrate_switch=message.bitrate_switch,
            is_error_frame=message.is_error_frame,
            channel=message.channel,
            timestamp=message.timestamp,
        )

    def __str__(self) -> str:  # noqa: D105 - trivial
        width = 8 if self.is_extended_id else 3
        hex_data = " ".join(f"{b:02X}" for b in self.data)
        return f"0x{self.arbitration_id:0{width}X} [{len(self.data)}] {hex_data}"


__all__ = ["DLC_TO_LENGTH", "LENGTH_TO_DLC", "length_to_dlc", "dlc_to_length", "CANFrame"]
