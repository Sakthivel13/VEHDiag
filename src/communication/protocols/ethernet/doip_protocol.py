"""DoIP (ISO 13400) protocol handler."""
from __future__ import annotations

import logging
import threading
from typing import Any

from ....core.enums.protocol_enums import ConnectionState, ProtocolType
from ....core.event_bus import EventBus, EventType
from ....core.exceptions import ProtocolError
from ....core.interfaces.i_vci_driver import IVCIDriver
from ....utils.network_utils import DOIP_PORT
from ....utils.timer_utils import PeriodicTimer
from ..base_protocol import BaseProtocol
from .doip_connection import DoIPConnection, VehicleAnnouncement
from .doip_message import (
    DoIPMessage,
    PayloadType,
    build_diagnostic_message,
    parse_diagnostic_message,
)
from .doip_routing import activate_routing, alive_check

_logger = logging.getLogger(__name__)


class DoIPProtocol(BaseProtocol):
    """UDS over Automotive Ethernet using DoIP.

    Args:
        driver: Unused for DoIP (kept for API symmetry with the CAN handlers).
        config: Mapping with ``host``, ``port``, ``source_address``,
            ``target_address``, ``activation_type``, ``use_tls`` and
            ``alive_check_interval_ms``.
        event_bus: Bus used for communication notifications.
    """

    def __init__(
        self,
        driver: IVCIDriver | None = None,
        config: dict[str, Any] | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        """Store the endpoint configuration without connecting."""
        super().__init__(driver, config, event_bus)  # type: ignore[arg-type]
        self.host = str(self.config.get("host", "127.0.0.1"))
        self.port = int(self.config.get("port", DOIP_PORT))
        self.source_address = int(self.config.get("source_address", 0x0E00))
        self.target_address = int(self.config.get("target_address", 0x1000))
        self.activation_type = int(self.config.get("activation_type", 0x00))
        self.use_tls = bool(self.config.get("use_tls", False))
        self.alive_interval_ms = float(self.config.get("alive_check_interval_ms", 0))
        self.connection: DoIPConnection | None = None
        self._alive_timer: PeriodicTimer | None = None
        self._lock = threading.RLock()

    @property
    def protocol_type(self) -> ProtocolType:
        """Return :attr:`ProtocolType.DOIP`."""
        return ProtocolType.DOIP

    # -- lifecycle ----------------------------------------------------------
    def initialize(self) -> None:
        """Open the TCP connection and activate routing.

        Raises:
            ProtocolError: Routing activation was refused by the entity.
        """
        self._set_state(ConnectionState.CONNECTING)
        self.connection = DoIPConnection(self.host, self.port, self.use_tls)
        try:
            self.connection.open()
            result = activate_routing(self.connection, self.source_address, self.activation_type)
            if not result.success:
                raise ProtocolError(
                    "DoIP routing activation was refused", {"reason": result.description}
                )
        except Exception:
            self._set_state(ConnectionState.ERROR)
            if self.connection is not None:
                self.connection.close()
                self.connection = None
            raise
        self._set_state(ConnectionState.CONNECTED)
        self._start_alive_checks()
        _logger.info(
            "DoIP ready %s:%d source=0x%04X target=0x%04X",
            self.host,
            self.port,
            self.source_address,
            self.target_address,
        )

    def shutdown(self) -> None:
        """Stop the alive check and close the connection."""
        if self._alive_timer is not None:
            self._alive_timer.stop()
            self._alive_timer = None
        if self.connection is not None:
            self.connection.close()
            self.connection = None
        super().shutdown()

    # -- exchanges ------------------------------------------------------------
    def send_message(self, payload: bytes, functional: bool = False) -> None:
        """Send a UDS payload wrapped into a DoIP diagnostic message."""
        self._require_connection()
        assert self.connection is not None
        target = 0xE400 if functional else self.target_address
        message = build_diagnostic_message(self.source_address, target, payload)
        self.connection.send(message)
        self.bus.publish(
            EventType.COMM_MESSAGE_TX,
            {"protocol": "DOIP", "payload": payload, "target": target},
            type(self).__name__,
        )

    def receive_message(self, timeout: float = 1.0) -> bytes | None:
        """Return the next UDS payload, skipping acknowledgements."""
        self._require_connection()
        assert self.connection is not None
        remaining = timeout
        while remaining > 0:
            message = self.connection.receive(remaining)
            if message is None:
                return None
            if message.payload_type == PayloadType.DIAGNOSTIC_MESSAGE:
                _source, _target, uds = parse_diagnostic_message(message)
                self.bus.publish(
                    EventType.COMM_MESSAGE_RX,
                    {"protocol": "DOIP", "payload": uds},
                    type(self).__name__,
                )
                return uds
            if message.payload_type == PayloadType.DIAGNOSTIC_MESSAGE_NACK:
                code = message.payload[4] if len(message.payload) > 4 else 0xFF
                raise ProtocolError(
                    "the DoIP entity rejected the diagnostic message",
                    {"nack": f"0x{code:02X}"},
                )
            if message.payload_type == PayloadType.ALIVE_CHECK_REQUEST:
                self.connection.send(DoIPMessage(PayloadType.ALIVE_CHECK_RESPONSE,
                                                 self.source_address.to_bytes(2, "big")))
            remaining -= 0.01
        return None

    def request(self, payload: bytes, timeout: float = 2.0, functional: bool = False) -> bytes | None:
        """Send *payload* and wait for the diagnostic answer."""
        self.send_message(payload, functional=functional)
        return self.receive_message(timeout)

    # -- helpers ---------------------------------------------------------------
    @staticmethod
    def discover(timeout: float = 2.0) -> list[VehicleAnnouncement]:
        """Broadcast a vehicle identification request and list the answers."""
        return DoIPConnection.discover(timeout)

    def check_alive(self) -> bool:
        """Send an alive check on the open connection."""
        if self.connection is None:
            return False
        return alive_check(self.connection)

    def _start_alive_checks(self) -> None:
        """Start the periodic alive check when configured."""
        if self.alive_interval_ms <= 0:
            return
        self._alive_timer = PeriodicTimer(
            self.alive_interval_ms / 1000.0, self._alive_tick, "doip-alive"
        )
        self._alive_timer.start()

    def _alive_tick(self) -> None:
        """Send one alive check and report a lost connection."""
        if not self.check_alive():
            self.bus.publish(
                EventType.COMM_ERROR,
                {"protocol": "DOIP", "error": "alive check failed"},
                type(self).__name__,
            )

    def get_protocol_info(self) -> dict[str, Any]:
        """Return the DoIP endpoint configuration."""
        info = super().get_protocol_info()
        info.update(
            {
                "host": self.host,
                "port": self.port,
                "source_address": f"0x{self.source_address:04X}",
                "target_address": f"0x{self.target_address:04X}",
                "tls": self.use_tls,
            }
        )
        return info


__all__ = ["DoIPProtocol"]
