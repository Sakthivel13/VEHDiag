"""SAE J1939 protocol handler."""
from __future__ import annotations

import logging
import queue
import threading
from typing import Any

from ....core.enums.protocol_enums import ConnectionState, MessageDirection, ProtocolType
from ....core.event_bus import EventBus, EventType
from ....core.interfaces.i_vci_driver import IVCIDriver
from ....core.models.message_model import BusMessage
from ..base_protocol import BaseProtocol
from .j1939_address_claim import AddressClaimer, J1939Name
from .j1939_dm_messages import (
    DM1_PGN,
    DM2_PGN,
    DiagnosticMessage,
    build_dm3_request,
    build_dm11_request,
    parse_dm,
)
from .j1939_pgn import GLOBAL_ADDRESS, J1939Id, pgn_to_bytes
from .j1939_transport import J1939TransportProtocol

_logger = logging.getLogger(__name__)

#: PGN used to request another PGN from a node.
REQUEST_PGN = 0x00EA00


class J1939Protocol(BaseProtocol):
    """Diagnostics over SAE J1939.

    Args:
        driver: VCI driver used to move 29-bit CAN frames.
        config: Mapping with ``source_address`` and ``bitrate``.
        event_bus: Bus used for communication notifications.
    """

    def __init__(
        self,
        driver: IVCIDriver,
        config: dict[str, Any] | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        """Store the configuration and build the transport engine."""
        super().__init__(driver, config, event_bus)
        self.source_address = int(self.config.get("source_address", 0xF9))
        self.transport = J1939TransportProtocol(self._send_raw)
        self.claimer = AddressClaimer(self._send_raw, J1939Name(), self.source_address)
        self._rx_queue: queue.Queue[tuple[int, bytes]] = queue.Queue(maxsize=4096)
        self._reader: threading.Thread | None = None
        self._stop = threading.Event()

    @property
    def protocol_type(self) -> ProtocolType:
        """Return :attr:`ProtocolType.J1939`."""
        return ProtocolType.J1939

    # -- lifecycle ----------------------------------------------------------
    def initialize(self) -> None:
        """Start the reader thread and claim the configured address."""
        self._set_state(ConnectionState.CONNECTING)
        if not self.driver.is_connected:
            self.driver.connect()
        self._stop.clear()
        self._reader = threading.Thread(target=self._read_loop, name="j1939-rx", daemon=True)
        self._reader.start()
        self._set_state(ConnectionState.CONNECTED)
        self.claimer.claim(self.source_address)

    def shutdown(self) -> None:
        """Stop the reader thread."""
        self._stop.set()
        if self._reader is not None and self._reader.is_alive():
            self._reader.join(1.0)
        self._reader = None
        super().shutdown()

    # -- messaging ------------------------------------------------------------
    def send_message(self, payload: bytes, functional: bool = False) -> None:
        """Send a payload on the proprietary A PGN (0xEF00)."""
        destination = GLOBAL_ADDRESS if functional else int(self.config.get("target_address", GLOBAL_ADDRESS))
        self.transport.send(0x00EF00, payload, self.source_address, destination)

    def receive_message(self, timeout: float = 1.0) -> bytes | None:
        """Return the next reassembled payload, or ``None`` on timeout."""
        try:
            _pgn, data = self._rx_queue.get(timeout=max(0.001, timeout))
            return data
        except queue.Empty:
            return None

    def send_pgn(self, pgn: int, data: bytes, destination: int = GLOBAL_ADDRESS) -> None:
        """Send *data* for *pgn*, using the transport protocol when needed."""
        self._require_connection()
        self.transport.send(pgn, data, self.source_address, destination)

    def request_pgn(self, pgn: int, destination: int = GLOBAL_ADDRESS, timeout: float = 2.0) -> bytes | None:
        """Request *pgn* from a node and wait for the answer."""
        self._require_connection()
        can_id = J1939Id(
            priority=6,
            pgn=REQUEST_PGN,
            source_address=self.source_address,
            destination_address=destination,
        ).to_can_id()
        self._send_raw(can_id, pgn_to_bytes(pgn).ljust(8, b"\xff"))
        deadline_queue: list[tuple[int, bytes]] = []
        try:
            while True:
                received_pgn, data = self._rx_queue.get(timeout=timeout)
                if received_pgn == pgn:
                    for item in deadline_queue:
                        self._rx_queue.put(item)
                    return data
                deadline_queue.append((received_pgn, data))
        except queue.Empty:
            for item in deadline_queue:
                self._rx_queue.put(item)
            return None

    # -- diagnostic messages ------------------------------------------------------
    def read_active_dtcs(self, timeout: float = 2.0) -> DiagnosticMessage | None:
        """Request DM1 (active DTCs) and parse the answer."""
        payload = self.request_pgn(DM1_PGN, timeout=timeout)
        return None if payload is None else parse_dm(payload, DM1_PGN)

    def read_previously_active_dtcs(self, timeout: float = 2.0) -> DiagnosticMessage | None:
        """Request DM2 (previously active DTCs) and parse the answer."""
        payload = self.request_pgn(DM2_PGN, timeout=timeout)
        return None if payload is None else parse_dm(payload, DM2_PGN)

    def clear_previously_active_dtcs(self, destination: int = GLOBAL_ADDRESS) -> None:
        """Send DM3 to clear previously active DTCs."""
        self._require_connection()
        can_id, payload = build_dm3_request(self.source_address, destination)
        self._send_raw(can_id, payload)

    def clear_active_dtcs(self, destination: int = GLOBAL_ADDRESS) -> None:
        """Send DM11 to clear active DTCs."""
        self._require_connection()
        can_id, payload = build_dm11_request(self.source_address, destination)
        self._send_raw(can_id, payload)

    # -- raw plumbing ----------------------------------------------------------------
    def _send_raw(self, can_id: int, payload: bytes) -> None:
        """Transmit one 29-bit CAN frame."""
        message = BusMessage(
            data=payload,
            arbitration_id=can_id,
            direction=MessageDirection.TX,
            protocol=ProtocolType.J1939,
            is_extended_id=True,
        )
        self.driver.send(message)
        self.bus.publish(EventType.COMM_MESSAGE_TX, {"message": message}, type(self).__name__)

    def _read_loop(self) -> None:
        """Background thread feeding received frames into the transport engine."""
        while not self._stop.is_set():
            if not self.driver.is_connected:
                return
            try:
                message = self.driver.receive(timeout=0.05)
            except Exception:  # noqa: BLE001 - keep the reader alive
                continue
            if message is None:
                continue
            self.bus.publish(EventType.COMM_MESSAGE_RX, {"message": message}, type(self).__name__)
            assembled = self.transport.handle_frame(message.arbitration_id, message.data)
            if assembled is not None:
                self._offer(assembled)
                continue
            identifier = J1939Id.from_can_id(message.arbitration_id)
            self._offer((identifier.pgn, message.data))

    def _offer(self, item: tuple[int, bytes]) -> None:
        """Place a reassembled message into the RX queue, dropping on overflow."""
        try:
            self._rx_queue.put_nowait(item)
        except queue.Full:
            _logger.warning("J1939 RX queue overflow")

    def get_protocol_info(self) -> dict[str, Any]:
        """Return the J1939 configuration and claim state."""
        info = super().get_protocol_info()
        info.update(
            {
                "source_address": f"0x{self.source_address:02X}",
                "claimed": self.claimer.claimed,
                "active_sessions": len(self.transport.sessions),
            }
        )
        return info


__all__ = ["J1939Protocol", "REQUEST_PGN"]
