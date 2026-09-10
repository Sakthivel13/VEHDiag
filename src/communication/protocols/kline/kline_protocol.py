"""K-Line protocol handler built on :mod:`pyserial`.

The handler owns the serial port, performs the initialisation sequence and
frames diagnostic payloads according to ISO 9141-2 or ISO 14230 (KWP2000).
"""
from __future__ import annotations

import logging
import time
from typing import Any

from ....core.enums.protocol_enums import ConnectionState, KLineInitType, ProtocolType
from ....core.event_bus import EventBus
from ....core.exceptions import ConnectionFailedError, DriverNotFoundError, ProtocolError
from ....core.interfaces.i_vci_driver import IVCIDriver
from ..base_protocol import BaseProtocol
from .kline_framing import build_iso9141_frame, build_iso14230_frame, parse_frame, strip_echo
from .kline_init_sequence import InitResult, fast_init, five_baud_init
from .kline_timing import KLineTiming

_logger = logging.getLogger(__name__)


class KLineProtocol(BaseProtocol):
    """UDS/KWP2000 over a K-Line serial interface.

    Args:
        driver: Present for API symmetry; K-Line uses the serial port directly.
        config: Mapping with ``port``, ``baudrate``, ``init_type``,
            ``address_byte``, ``echo_cancellation`` and the P1..P4 timings.
        event_bus: Bus used for communication notifications.
    """

    def __init__(
        self,
        driver: IVCIDriver | None = None,
        config: dict[str, Any] | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        """Store the serial configuration without opening the port."""
        super().__init__(driver, config, event_bus)  # type: ignore[arg-type]
        self.port_name = str(self.config.get("port", ""))
        self.baudrate = int(self.config.get("baudrate", 10400))
        self.init_type = KLineInitType(str(self.config.get("init_type", "FAST_INIT")))
        self.address_byte = int(self.config.get("address_byte", 0x33))
        self.tester_address = int(self.config.get("tester_address", 0xF1))
        self.echo_cancellation = bool(self.config.get("echo_cancellation", True))
        self.use_kwp_framing = self.init_type is not KLineInitType.FIVE_BAUD
        self.timing = KLineTiming(
            p1_ms=float(self.config.get("p1_ms", 5)),
            p2_ms=float(self.config.get("p2_ms", 50)),
            p3_ms=float(self.config.get("p3_ms", 55)),
            p4_ms=float(self.config.get("p4_ms", 5)),
        )
        self.init_result: InitResult | None = None
        self._serial: Any = None
        self._last_request: bytes = b""

    @property
    def protocol_type(self) -> ProtocolType:
        """Return :attr:`ProtocolType.KLINE`."""
        return ProtocolType.KLINE

    # -- lifecycle ----------------------------------------------------------
    def initialize(self) -> None:
        """Open the serial port and run the configured init sequence.

        Raises:
            DriverNotFoundError: pyserial is not installed.
            ConnectionFailedError: The port could not be opened.
            ProtocolError: The ECU did not answer the init sequence.
        """
        self._set_state(ConnectionState.CONNECTING)
        try:
            import serial  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - declared dependency
            self._set_state(ConnectionState.ERROR)
            raise DriverNotFoundError("pyserial is required for K-Line") from exc
        if not self.port_name:
            self._set_state(ConnectionState.ERROR)
            raise ConnectionFailedError("no serial port configured for K-Line")
        try:
            self._serial = serial.Serial(
                port=self.port_name,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timing.byte_timeout_s(),
                write_timeout=1.0,
            )
        except Exception as exc:  # noqa: BLE001
            self._set_state(ConnectionState.ERROR)
            raise ConnectionFailedError(
                f"could not open the serial port {self.port_name}", {"cause": str(exc)}
            ) from exc

        if self.init_type is KLineInitType.FIVE_BAUD:
            self.init_result = five_baud_init(self._serial, self.address_byte, self.timing)
            self.use_kwp_framing = False
        elif self.init_type is KLineInitType.FAST_INIT:
            self.init_result = fast_init(self._serial, timing=self.timing)
            self.use_kwp_framing = True
        else:
            self.init_result = InitResult(True, message="initialisation skipped")

        if not self.init_result.success:
            self._set_state(ConnectionState.ERROR)
            raise ProtocolError(
                "K-Line initialisation failed", {"detail": self.init_result.message}
            )
        self._set_state(ConnectionState.CONNECTED)
        _logger.info(
            "K-Line ready on %s (%s, %s)",
            self.port_name,
            self.init_type.value,
            self.init_result.protocol_hint,
        )

    def shutdown(self) -> None:
        """Close the serial port."""
        if self._serial is not None:
            try:
                self._serial.close()
            finally:
                self._serial = None
        super().shutdown()

    # -- exchanges ------------------------------------------------------------
    def send_message(self, payload: bytes, functional: bool = False) -> None:
        """Frame and transmit *payload* on the K-Line."""
        self._require_connection()
        target = 0x33 if functional else self.address_byte
        if self.use_kwp_framing:
            frame = build_iso14230_frame(payload, target, self.tester_address)
        else:
            frame = build_iso9141_frame(payload, target, self.tester_address)
        time.sleep(self.timing.p3_ms / 1000.0)
        self._serial.reset_input_buffer()
        self._serial.write(frame)
        self._serial.flush()
        self._last_request = frame
        if self.echo_cancellation:
            self._serial.read(len(frame))

    def receive_message(self, timeout: float = 1.0) -> bytes | None:
        """Read and decode one K-Line response."""
        self._require_connection()
        deadline = time.perf_counter() + max(timeout, self.timing.response_timeout_s())
        buffer = bytearray()
        while time.perf_counter() < deadline:
            chunk = self._serial.read(64)
            if chunk:
                buffer.extend(chunk)
                # Keep reading until the inter-byte gap indicates the end.
                idle_until = time.perf_counter() + self.timing.p1_ms * 4 / 1000.0
                while time.perf_counter() < idle_until:
                    more = self._serial.read(64)
                    if more:
                        buffer.extend(more)
                        idle_until = time.perf_counter() + self.timing.p1_ms * 4 / 1000.0
                break
            time.sleep(0.005)
        if not buffer:
            return None
        raw = strip_echo(self._last_request, bytes(buffer)) if self.echo_cancellation else bytes(buffer)
        if not raw:
            return None
        return parse_frame(raw).data

    def request(self, payload: bytes, timeout: float = 1.0) -> bytes | None:
        """Send *payload* and read the response in one call."""
        self.send_message(payload)
        return self.receive_message(timeout)

    def get_protocol_info(self) -> dict[str, Any]:
        """Return the K-Line configuration and init results."""
        info = super().get_protocol_info()
        info.update(
            {
                "port": self.port_name,
                "baudrate": self.baudrate,
                "init_type": self.init_type.value,
                "kwp_framing": self.use_kwp_framing,
                "key_bytes": list(self.init_result.key_bytes) if self.init_result else [],
                "protocol_hint": self.init_result.protocol_hint if self.init_result else "",
            }
        )
        return info


__all__ = ["KLineProtocol"]
