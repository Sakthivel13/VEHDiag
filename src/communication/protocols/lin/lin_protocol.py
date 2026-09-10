"""LIN protocol handler with diagnostic transport support."""
from __future__ import annotations

import logging
import time
from typing import Any

from ....core.enums.protocol_enums import ConnectionState, ProtocolType
from ....core.event_bus import EventBus
from ....core.exceptions import ConnectionFailedError, DriverNotFoundError
from ....core.interfaces.i_vci_driver import IVCIDriver
from ..base_protocol import BaseProtocol
from .lin_frame import (
    MASTER_REQUEST_ID,
    SLAVE_RESPONSE_ID,
    LINFrame,
    build_master_request,
    parse_slave_response,
)
from .lin_scheduler import LINScheduler, ScheduleTable

_logger = logging.getLogger(__name__)


class LINProtocol(BaseProtocol):
    """Diagnostics over LIN using the 0x3C/0x3D frame pair.

    Args:
        driver: Optional VCI driver; when omitted a serial port is used.
        config: Mapping with ``port``, ``baudrate``, ``nad`` and
            ``enhanced_checksum``.
        event_bus: Bus used for communication notifications.
    """

    def __init__(
        self,
        driver: IVCIDriver | None = None,
        config: dict[str, Any] | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        """Store the LIN configuration without opening the interface."""
        super().__init__(driver, config, event_bus)  # type: ignore[arg-type]
        self.port_name = str(self.config.get("port", ""))
        self.baudrate = int(self.config.get("baudrate", 19200))
        self.nad = int(self.config.get("nad", 0x01))
        self.enhanced_checksum = bool(self.config.get("enhanced_checksum", True))
        self.break_bits = int(self.config.get("break_bits", 13))
        self.schedule = LINScheduler(self.send_frame, ScheduleTable())
        self._serial: Any = None

    @property
    def protocol_type(self) -> ProtocolType:
        """Return :attr:`ProtocolType.LIN`."""
        return ProtocolType.LIN

    # -- lifecycle ----------------------------------------------------------
    def initialize(self) -> None:
        """Open the LIN interface.

        Raises:
            DriverNotFoundError: pyserial is unavailable for a serial adapter.
            ConnectionFailedError: The interface could not be opened.
        """
        self._set_state(ConnectionState.CONNECTING)
        if self.driver is not None:
            if not self.driver.is_connected:
                self.driver.connect()
            self._set_state(ConnectionState.CONNECTED)
            return
        try:
            import serial  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - declared dependency
            self._set_state(ConnectionState.ERROR)
            raise DriverNotFoundError("pyserial is required for serial LIN adapters") from exc
        if not self.port_name:
            self._set_state(ConnectionState.ERROR)
            raise ConnectionFailedError("no serial port configured for LIN")
        try:
            self._serial = serial.Serial(self.port_name, self.baudrate, timeout=0.1)
        except Exception as exc:  # noqa: BLE001
            self._set_state(ConnectionState.ERROR)
            raise ConnectionFailedError(
                f"could not open the LIN port {self.port_name}", {"cause": str(exc)}
            ) from exc
        self._set_state(ConnectionState.CONNECTED)

    def shutdown(self) -> None:
        """Stop the schedule and close the interface."""
        self.schedule.stop()
        if self._serial is not None:
            try:
                self._serial.close()
            finally:
                self._serial = None
        super().shutdown()

    # -- frame level -----------------------------------------------------------
    def send_frame(self, frame: LINFrame) -> None:
        """Transmit one LIN frame including break and sync fields."""
        self._require_connection()
        if self._serial is not None:
            self._serial.break_condition = True
            time.sleep(self.break_bits / self.baudrate)
            self._serial.break_condition = False
            self._serial.write(bytes([0x55]) + frame.to_bytes())
            self._serial.flush()
            return
        if self.driver is not None:
            from ....core.models.message_model import BusMessage

            self.driver.send(
                BusMessage(
                    data=frame.data,
                    arbitration_id=frame.frame_id,
                    protocol=ProtocolType.LIN,
                )
            )

    def read_frame(self, timeout: float = 0.5) -> LINFrame | None:
        """Read one LIN frame from the interface."""
        self._require_connection()
        if self._serial is not None:
            deadline = time.perf_counter() + timeout
            buffer = bytearray()
            while time.perf_counter() < deadline:
                chunk = self._serial.read(16)
                if chunk:
                    buffer.extend(chunk)
                if len(buffer) >= 10:
                    break
            if len(buffer) < 3:
                return None
            payload = bytes(buffer).lstrip(b"\x00")
            if payload.startswith(b"\x55"):
                payload = payload[1:]
            return LINFrame.from_bytes(payload, self.enhanced_checksum)
        if self.driver is not None:
            message = self.driver.receive(timeout)
            if message is None:
                return None
            return LINFrame(message.arbitration_id, message.data, self.enhanced_checksum)
        return None

    # -- diagnostic transport -----------------------------------------------------
    def send_message(self, payload: bytes, functional: bool = False) -> None:
        """Send a diagnostic payload as a master request frame."""
        nad = 0x7F if functional else self.nad
        self.send_frame(build_master_request(nad, payload))

    def receive_message(self, timeout: float = 1.0) -> bytes | None:
        """Poll the slave response frame and return the diagnostic payload."""
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            self.send_frame(LINFrame(SLAVE_RESPONSE_ID, b"", enhanced=False))
            frame = self.read_frame(0.05)
            if frame is not None and frame.frame_id == SLAVE_RESPONSE_ID and frame.data:
                try:
                    _nad, payload = parse_slave_response(frame)
                except Exception:  # noqa: BLE001 - keep polling
                    continue
                if payload:
                    return payload
            time.sleep(0.01)
        return None

    def request(self, payload: bytes, timeout: float = 1.0) -> bytes | None:
        """Send *payload* and poll for the slave response."""
        self.send_message(payload)
        return self.receive_message(timeout)

    def get_protocol_info(self) -> dict[str, Any]:
        """Return the LIN configuration and schedule state."""
        info = super().get_protocol_info()
        info.update(
            {
                "port": self.port_name,
                "baudrate": self.baudrate,
                "nad": f"0x{self.nad:02X}",
                "enhanced_checksum": self.enhanced_checksum,
                "schedule_running": self.schedule.is_running,
                "schedule_cycles": self.schedule.cycles,
                "master_request_id": f"0x{MASTER_REQUEST_ID:02X}",
            }
        )
        return info


__all__ = ["LINProtocol"]
