"""FlexRay protocol handler with ISO 10681 transport."""
from __future__ import annotations

import logging
import queue
import threading
from typing import Any

from ....core.enums.protocol_enums import ConnectionState, MessageDirection, ProtocolType
from ....core.event_bus import EventBus, EventType
from ....core.exceptions import ProtocolError
from ....core.interfaces.i_vci_driver import IVCIDriver
from ....core.models.message_model import BusMessage
from ..base_protocol import BaseProtocol
from .flexray_cluster import FlexRayCluster
from .flexray_fibex_parser import parse_fibex
from .flexray_frame import FlexRayChannel, FlexRayFrame

_logger = logging.getLogger(__name__)

#: ISO 10681-2 PCI types for the FlexRay transport protocol.
FR_TP_SF = 0x0
FR_TP_FF = 0x1
FR_TP_CF = 0x2
FR_TP_FC = 0x3


class FlexRayProtocol(BaseProtocol):
    """UDS over FlexRay using the ISO 10681 transport protocol.

    Args:
        driver: VCI driver capable of FlexRay communication.
        config: Mapping with ``config_file`` (FIBEX), ``tx_slot``, ``rx_slot``
            and ``channels``.
        event_bus: Bus used for communication notifications.
    """

    def __init__(
        self,
        driver: IVCIDriver,
        config: dict[str, Any] | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        """Store the configuration and load the FIBEX file when given."""
        super().__init__(driver, config, event_bus)
        self.tx_slot = int(self.config.get("tx_slot", 40))
        self.rx_slot = int(self.config.get("rx_slot", 41))
        self.channels = FlexRayChannel(str(self.config.get("channels", "AB")))
        self.cluster: FlexRayCluster = FlexRayCluster()
        config_file = str(self.config.get("config_file", ""))
        if config_file:
            self.cluster = parse_fibex(config_file)
        self._rx_queue: queue.Queue[bytes] = queue.Queue(maxsize=1024)
        self._reader: threading.Thread | None = None
        self._stop = threading.Event()
        self._rx_buffer = bytearray()
        self._rx_expected = 0

    @property
    def protocol_type(self) -> ProtocolType:
        """Return :attr:`ProtocolType.FLEXRAY`."""
        return ProtocolType.FLEXRAY

    # -- lifecycle ----------------------------------------------------------
    def initialize(self) -> None:
        """Validate the cluster configuration and start the reader thread.

        Raises:
            ProtocolError: The cluster configuration is inconsistent.
        """
        self._set_state(ConnectionState.CONNECTING)
        problems = self.cluster.validate()
        if problems and self.config.get("strict_cluster_validation", False):
            self._set_state(ConnectionState.ERROR)
            raise ProtocolError("invalid FlexRay cluster configuration", {"problems": problems})
        for problem in problems:
            _logger.warning("FlexRay cluster: %s", problem)
        if not self.driver.is_connected:
            self.driver.connect()
        self._stop.clear()
        self._reader = threading.Thread(target=self._read_loop, name="flexray-rx", daemon=True)
        self._reader.start()
        self._set_state(ConnectionState.CONNECTED)

    def shutdown(self) -> None:
        """Stop the reader thread."""
        self._stop.set()
        if self._reader is not None and self._reader.is_alive():
            self._reader.join(1.0)
        self._reader = None
        super().shutdown()

    # -- transport ------------------------------------------------------------
    def send_message(self, payload: bytes, functional: bool = False) -> None:
        """Send a UDS payload, segmenting it per ISO 10681 when required."""
        self._require_connection()
        capacity = int(self.config.get("payload_size", 32))
        if len(payload) <= capacity - 1:
            body = bytes([(FR_TP_SF << 4) | len(payload)]) + payload
            self._send_frame(FlexRayFrame(self.tx_slot, payload=body, channel=self.channels))
            return
        header = bytes([(FR_TP_FF << 4) | (len(payload) >> 8), len(payload) & 0xFF])
        first = payload[: capacity - 2]
        self._send_frame(FlexRayFrame(self.tx_slot, payload=header + first, channel=self.channels))
        index, sequence = len(first), 1
        while index < len(payload):
            chunk = payload[index : index + capacity - 1]
            body = bytes([(FR_TP_CF << 4) | (sequence & 0x0F)]) + chunk
            self._send_frame(FlexRayFrame(self.tx_slot, payload=body, channel=self.channels))
            index += len(chunk)
            sequence = (sequence + 1) & 0x0F

    def receive_message(self, timeout: float = 1.0) -> bytes | None:
        """Return the next reassembled UDS payload, or ``None`` on timeout."""
        self._require_connection()
        try:
            return self._rx_queue.get(timeout=max(0.001, timeout))
        except queue.Empty:
            return None

    def _send_frame(self, frame: FlexRayFrame) -> None:
        """Transmit one FlexRay frame through the driver."""
        frame.validate()
        message = BusMessage(
            data=frame.payload,
            arbitration_id=frame.slot_id,
            direction=MessageDirection.TX,
            protocol=ProtocolType.FLEXRAY,
            metadata={"cycle": frame.cycle, "channel": frame.channel.value},
        )
        self.driver.send(message)
        self.bus.publish(EventType.COMM_MESSAGE_TX, {"message": message}, type(self).__name__)

    def _read_loop(self) -> None:
        """Background thread reassembling ISO 10681 payloads."""
        while not self._stop.is_set():
            if not self.driver.is_connected:
                return
            try:
                message = self.driver.receive(timeout=0.05)
            except Exception:  # noqa: BLE001 - keep the reader alive
                continue
            if message is None or message.arbitration_id != self.rx_slot:
                continue
            self.bus.publish(EventType.COMM_MESSAGE_RX, {"message": message}, type(self).__name__)
            payload = self._reassemble(message.data)
            if payload is not None:
                try:
                    self._rx_queue.put_nowait(payload)
                except queue.Full:
                    _logger.warning("FlexRay RX queue overflow")

    def _reassemble(self, data: bytes) -> bytes | None:
        """Feed one frame payload into the reassembly buffer."""
        if not data:
            return None
        pci = data[0] >> 4
        if pci == FR_TP_SF:
            length = data[0] & 0x0F
            return bytes(data[1 : 1 + length])
        if pci == FR_TP_FF:
            self._rx_expected = ((data[0] & 0x0F) << 8) | data[1]
            self._rx_buffer = bytearray(data[2:])
            return None
        if pci == FR_TP_CF and self._rx_expected:
            self._rx_buffer.extend(data[1:])
            if len(self._rx_buffer) >= self._rx_expected:
                payload = bytes(self._rx_buffer[: self._rx_expected])
                self._rx_buffer.clear()
                self._rx_expected = 0
                return payload
        return None

    def get_protocol_info(self) -> dict[str, Any]:
        """Return the FlexRay cluster and slot configuration."""
        info = super().get_protocol_info()
        info.update(
            {
                "tx_slot": self.tx_slot,
                "rx_slot": self.rx_slot,
                "channels": self.channels.value,
                "cluster": self.cluster.to_dict(),
                "cluster_problems": self.cluster.validate(),
            }
        )
        return info


__all__ = ["FlexRayProtocol", "FR_TP_SF", "FR_TP_FF", "FR_TP_CF", "FR_TP_FC"]
