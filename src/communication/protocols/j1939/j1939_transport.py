"""J1939 transport protocol (TP.CM and TP.DT) for payloads above eight bytes."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Callable

from ....core.exceptions import ProtocolError
from .j1939_pgn import GLOBAL_ADDRESS, J1939Id, bytes_to_pgn, pgn_to_bytes

_logger = logging.getLogger(__name__)

#: PGN of the connection management messages.
TP_CM_PGN = 0x00EC00
#: PGN of the data transfer messages.
TP_DT_PGN = 0x00EB00
#: Largest payload the transport protocol can carry.
MAX_TP_SIZE = 1785


class ControlByte(IntEnum):
    """TP.CM control bytes."""

    RTS = 0x10
    CTS = 0x11
    END_OF_MSG_ACK = 0x13
    BAM = 0x20
    ABORT = 0xFF


class AbortReason(IntEnum):
    """Connection abort reasons."""

    ALREADY_IN_SESSION = 1
    RESOURCES_BUSY = 2
    TIMEOUT = 3
    UNEXPECTED_DATA = 4
    UNKNOWN = 250


@dataclass(slots=True)
class TransportSession:
    """State of one in-progress transport protocol session."""

    pgn: int
    total_size: int
    packet_count: int
    source_address: int
    destination_address: int = GLOBAL_ADDRESS
    broadcast: bool = False
    received: dict[int, bytes] = field(default_factory=dict)

    @property
    def complete(self) -> bool:
        """Return ``True`` once every packet has been received."""
        return len(self.received) >= self.packet_count

    def assemble(self) -> bytes:
        """Concatenate the received packets and trim to the declared size."""
        data = bytearray()
        for index in range(1, self.packet_count + 1):
            data.extend(self.received.get(index, b"\xff" * 7))
        return bytes(data[: self.total_size])


def build_bam(pgn: int, size: int, source: int) -> tuple[int, bytes]:
    """Build a Broadcast Announce Message.

    Returns:
        Tuple of ``(can_id, payload)`` ready to be transmitted.

    Example:
        >>> can_id, payload = build_bam(0x00FECA, 20, 0x00)
        >>> payload[0] == 0x20
        True
    """
    packets = (size + 6) // 7
    payload = bytes([ControlByte.BAM, size & 0xFF, (size >> 8) & 0xFF, packets, 0xFF]) + pgn_to_bytes(pgn)
    can_id = J1939Id(priority=7, pgn=TP_CM_PGN, source_address=source,
                     destination_address=GLOBAL_ADDRESS).to_can_id()
    return can_id, payload


def build_rts(pgn: int, size: int, source: int, destination: int) -> tuple[int, bytes]:
    """Build a Request To Send message for a destination specific transfer."""
    packets = (size + 6) // 7
    payload = bytes([ControlByte.RTS, size & 0xFF, (size >> 8) & 0xFF, packets, 0xFF]) + pgn_to_bytes(pgn)
    can_id = J1939Id(priority=7, pgn=TP_CM_PGN, source_address=source,
                     destination_address=destination).to_can_id()
    return can_id, payload


def build_data_packets(data: bytes, source: int, destination: int = GLOBAL_ADDRESS) -> list[tuple[int, bytes]]:
    """Split *data* into TP.DT packets.

    Example:
        >>> len(build_data_packets(bytes(20), 0x00))
        3
    """
    can_id = J1939Id(priority=7, pgn=TP_DT_PGN, source_address=source,
                     destination_address=destination).to_can_id()
    packets: list[tuple[int, bytes]] = []
    for index in range(0, len(data), 7):
        sequence = index // 7 + 1
        chunk = data[index : index + 7].ljust(7, b"\xff")
        packets.append((can_id, bytes([sequence]) + chunk))
    return packets


class J1939TransportProtocol:
    """Reassembles multi-packet J1939 messages and sends BAM transfers.

    Args:
        send_raw: Callable transmitting ``(can_id, payload)``.
    """

    def __init__(self, send_raw: Callable[[int, bytes], None]) -> None:
        """Create the engine with no active sessions."""
        self.send_raw = send_raw
        self.sessions: dict[int, TransportSession] = {}

    def send(self, pgn: int, data: bytes, source: int, destination: int = GLOBAL_ADDRESS) -> None:
        """Send *data* using BAM (broadcast) or a single frame when short.

        Raises:
            ProtocolError: The payload exceeds the transport protocol limit.
        """
        if len(data) > MAX_TP_SIZE:
            raise ProtocolError(
                f"J1939 payload of {len(data)} bytes exceeds the {MAX_TP_SIZE} byte limit"
            )
        if len(data) <= 8:
            can_id = J1939Id(
                priority=6, pgn=pgn, source_address=source, destination_address=destination
            ).to_can_id()
            self.send_raw(can_id, data.ljust(8, b"\xff"))
            return
        cm_id, cm_payload = build_bam(pgn, len(data), source)
        self.send_raw(cm_id, cm_payload)
        for can_id, payload in build_data_packets(data, source, destination):
            self.send_raw(can_id, payload)

    def handle_frame(self, can_id: int, payload: bytes) -> tuple[int, bytes] | None:
        """Feed one received frame into the reassembly engine.

        Returns:
            ``(pgn, data)`` when a multi-packet message completed, else ``None``.
        """
        identifier = J1939Id.from_can_id(can_id)
        if identifier.pgn == TP_CM_PGN:
            self._handle_cm(identifier, payload)
            return None
        if identifier.pgn == TP_DT_PGN:
            return self._handle_dt(identifier, payload)
        return None

    def _handle_cm(self, identifier: J1939Id, payload: bytes) -> None:
        """Process a connection management frame."""
        if len(payload) < 8:
            return
        control = payload[0]
        if control in (ControlByte.BAM, ControlByte.RTS):
            size = payload[1] | (payload[2] << 8)
            packets = payload[3]
            pgn = bytes_to_pgn(payload[5:8])
            self.sessions[identifier.source_address] = TransportSession(
                pgn=pgn,
                total_size=size,
                packet_count=packets,
                source_address=identifier.source_address,
                destination_address=identifier.destination_address,
                broadcast=control == ControlByte.BAM,
            )
        elif control == ControlByte.ABORT:
            self.sessions.pop(identifier.source_address, None)

    def _handle_dt(self, identifier: J1939Id, payload: bytes) -> tuple[int, bytes] | None:
        """Process a data transfer frame and finish the session when complete."""
        session = self.sessions.get(identifier.source_address)
        if session is None or len(payload) < 2:
            return None
        session.received[payload[0]] = bytes(payload[1:8])
        if not session.complete:
            return None
        del self.sessions[identifier.source_address]
        return session.pgn, session.assemble()


__all__ = [
    "TP_CM_PGN",
    "TP_DT_PGN",
    "MAX_TP_SIZE",
    "ControlByte",
    "AbortReason",
    "TransportSession",
    "J1939TransportProtocol",
    "build_bam",
    "build_rts",
    "build_data_packets",
]
