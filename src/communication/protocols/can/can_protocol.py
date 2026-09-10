"""Classic CAN protocol handler with ISO-TP transport.

The handler owns an :class:`IsoTpHandler` and exposes the payload oriented
:class:`IProtocolHandler` API expected by the diagnostic layer. Raw frames are
moved by the injected :class:`IVCIDriver`, so the same code drives PCAN,
Vector, Kvaser, SocketCAN or the virtual bus.
"""
from __future__ import annotations

import logging
import queue
import threading
from dataclasses import asdict
from typing import Any

from ....core.enums.protocol_enums import (
    ConnectionState,
    IsoTpAddressingFormat,
    MessageDirection,
    ProtocolType,
)
from ....core.event_bus import EventBus, EventType
from ....core.interfaces.i_vci_driver import IVCIDriver
from ....core.models.message_model import BusMessage
from ...isotp_handler import IsoTpConfig, IsoTpHandler
from ..base_protocol import BaseProtocol
from .can_filter import CANFilterSet

_logger = logging.getLogger(__name__)


class CANProtocol(BaseProtocol):
    """UDS over classic CAN (ISO 15765-2 on ISO 11898-1).

    Args:
        driver: VCI driver used to send and receive raw frames.
        config: Mapping with the keys ``tx_id``, ``rx_id``, ``functional_id``,
            ``extended_id``, ``padding_enabled``, ``padding_byte`` and an
            optional nested ``isotp`` section.
        event_bus: Bus used to publish TX/RX notifications.

    Example:
        >>> from src.communication.vci_drivers.virtual.virtual_vci_driver import (
        ...     VirtualVCIDriver)
        >>> driver = VirtualVCIDriver()
        >>> driver.connect()
        >>> protocol = CANProtocol(driver)
        >>> protocol.initialize()
        >>> protocol.is_connected
        True
        >>> protocol.shutdown()
    """

    def __init__(
        self,
        driver: IVCIDriver,
        config: dict[str, Any] | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        """Build the handler and its ISO-TP engine."""
        super().__init__(driver, config, event_bus)
        self.tx_id: int = int(self.config.get("tx_id", 0x7E0))
        self.rx_id: int = int(self.config.get("rx_id", 0x7E8))
        self.functional_id: int = int(self.config.get("functional_id", 0x7DF))
        self.extended_id: bool = bool(self.config.get("extended_id", False))
        self.filters = CANFilterSet.for_diagnostics(self.rx_id, self.extended_id)

        isotp_cfg = dict(self.config.get("isotp", {}))
        self.isotp_config = IsoTpConfig(
            addressing_format=IsoTpAddressingFormat(
                isotp_cfg.get("addressing_format", "NORMAL_11BIT")
            ),
            block_size=int(isotp_cfg.get("block_size", 8)),
            st_min_ms=float(isotp_cfg.get("st_min_ms", 0)),
            n_bs_timeout_ms=float(isotp_cfg.get("n_bs_timeout_ms", 1000)),
            n_cr_timeout_ms=float(isotp_cfg.get("n_cr_timeout_ms", 1000)),
            n_ar_timeout_ms=float(isotp_cfg.get("n_ar_timeout_ms", 1000)),
            tx_padding=bool(self.config.get("padding_enabled", True)),
            padding_byte=int(self.config.get("padding_byte", 0x00)),
            can_fd=False,
            max_frame_size=8,
            source_address=int(isotp_cfg.get("source_address", 0)),
            target_address=int(isotp_cfg.get("target_address", 0)),
        )
        self._rx_queue: queue.Queue[bytes] = queue.Queue(maxsize=4096)
        self._reader: threading.Thread | None = None
        self._stop = threading.Event()
        self._tx_functional = False
        self.isotp = IsoTpHandler(self._send_raw_frame, self._next_raw_frame, self.isotp_config)

    # -- IProtocolHandler ---------------------------------------------------
    @property
    def protocol_type(self) -> ProtocolType:
        """Return :attr:`ProtocolType.CAN`."""
        return ProtocolType.CAN

    def initialize(self) -> None:
        """Start the receive thread and mark the protocol connected."""
        self._set_state(ConnectionState.CONNECTING)
        if not self.driver.is_connected:
            self.driver.connect()
        self._stop.clear()
        self._reader = threading.Thread(target=self._read_loop, name="can-rx", daemon=True)
        self._reader.start()
        self._set_state(ConnectionState.CONNECTED)
        _logger.info(
            "CAN protocol ready TX=0x%X RX=0x%X extended=%s", self.tx_id, self.rx_id, self.extended_id
        )

    def shutdown(self) -> None:
        """Stop the receive thread and release the ISO-TP state."""
        self._stop.set()
        if self._reader is not None and self._reader.is_alive():
            self._reader.join(1.0)
        self._reader = None
        self.isotp.reset()
        super().shutdown()

    def send_message(self, payload: bytes, functional: bool = False) -> None:
        """Send an assembled UDS payload, segmenting it when necessary."""
        self._require_connection()
        self._tx_functional = functional
        try:
            self.isotp.send(payload)
        finally:
            self._tx_functional = False

    def receive_message(self, timeout: float = 1.0) -> bytes | None:
        """Return the next assembled UDS payload, or ``None`` on timeout."""
        self._require_connection()
        return self.isotp.receive(timeout)

    def request(self, payload: bytes, timeout: float = 1.0, functional: bool = False) -> bytes | None:
        """Send *payload* and wait for one assembled response."""
        self.flush()
        self.send_message(payload, functional=functional)
        return self.receive_message(timeout)

    def flush(self) -> None:
        """Discard buffered frames and reset the reassembly state."""
        while True:
            try:
                self._rx_queue.get_nowait()
            except queue.Empty:
                break
        self.isotp.reset()

    def get_protocol_info(self) -> dict[str, Any]:
        """Return the configuration plus the ISO-TP statistics."""
        info = super().get_protocol_info()
        info.update(
            {
                "tx_id": f"0x{self.tx_id:X}",
                "rx_id": f"0x{self.rx_id:X}",
                "functional_id": f"0x{self.functional_id:X}",
                "extended_id": self.extended_id,
                "isotp": asdict(self.isotp.statistics),
            }
        )
        return info

    # -- configuration -----------------------------------------------------------
    def set_addressing(self, tx_id: int, rx_id: int, extended: bool | None = None) -> None:
        """Change the request/response identifiers at runtime."""
        self.tx_id, self.rx_id = tx_id, rx_id
        if extended is not None:
            self.extended_id = extended
        self.filters = CANFilterSet.for_diagnostics(self.rx_id, self.extended_id)

    # -- raw frame plumbing -------------------------------------------------------
    def _send_raw_frame(self, data: bytes) -> None:
        """Transmit one raw CAN frame carrying an ISO-TP PDU."""
        message = BusMessage(
            data=data,
            arbitration_id=self.functional_id if self._tx_functional else self.tx_id,
            direction=MessageDirection.TX,
            protocol=self.protocol_type,
            is_extended_id=self.extended_id,
        )
        self.driver.send(message)
        self.bus.publish(
            EventType.COMM_MESSAGE_TX,
            {"message": message},
            type(self).__name__,
        )

    def _next_raw_frame(self, timeout: float) -> bytes | None:
        """Return the payload of the next matching received frame."""
        if timeout <= 0:
            timeout = 0.001
        try:
            return self._rx_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def _read_loop(self) -> None:
        """Background thread copying matching frames into the RX queue.

        The loop exits as soon as the driver is closed so a forgotten
        ``shutdown`` can never leave a polling thread behind.
        """
        while not self._stop.is_set():
            if not self.driver.is_connected:
                return
            try:
                message = self.driver.receive(timeout=0.05)
            except Exception:  # noqa: BLE001 - keep the reader alive
                _logger.exception("CAN receive failed")
                continue
            if message is None:
                continue
            if not self.filters.accepts(message.arbitration_id, message.is_extended_id):
                continue
            self.bus.publish(
                EventType.COMM_MESSAGE_RX,
                {"message": message},
                type(self).__name__,
            )
            try:
                self._rx_queue.put_nowait(message.data)
            except queue.Full:
                _logger.warning("CAN RX queue overflow; dropping frame")


__all__ = ["CANProtocol"]
