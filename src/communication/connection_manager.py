"""Connection lifecycle orchestration.

The :class:`ConnectionManager` is the single object the UI talks to when the
operator presses *Connect*. It builds the VCI driver, the protocol handler and
the transport layer from the configuration, drives the state machine, performs
health checks and handles automatic reconnection.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import asdict, dataclass, field
from typing import Any

from ..core.configuration_manager import ConfigurationManager, get_config
from ..core.enums.protocol_enums import ConnectionState, ProtocolType
from ..core.enums.vci_enums import VCIType
from ..core.event_bus import EventBus, EventType, get_event_bus
from ..core.exceptions import ConnectionFailedError, UnsupportedProtocolError
from ..core.interfaces.i_protocol_handler import IProtocolHandler
from ..core.interfaces.i_vci_driver import IVCIDriver
from ..core.models.vci_model import VCIChannelConfig
from ..utils.timer_utils import PeriodicTimer
from .transport_layer import TransportLayer, TransportTiming
from .vci_drivers.vci_factory import VCIFactory

_logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ConnectionProfile:
    """A named, serialisable connection setup.

    Attributes:
        name: Display name of the profile.
        vci_type: Hardware family to use.
        channel: Channel index or interface name.
        protocol: Protocol to run on the channel.
        bitrate: Arbitration bitrate in bit/s.
        data_bitrate: CAN FD data phase bitrate.
        tx_id: Diagnostic request identifier.
        rx_id: Diagnostic response identifier.
        functional_id: Functional (broadcast) request identifier.
        extended_id: Use 29-bit identifiers.
        options: Protocol specific extra options (host, port, serial port...).
    """

    name: str = "Default"
    vci_type: VCIType = VCIType.VIRTUAL
    channel: int | str = 0
    protocol: ProtocolType = ProtocolType.CAN
    bitrate: int = 500_000
    data_bitrate: int = 2_000_000
    tx_id: int = 0x7E0
    rx_id: int = 0x7E8
    functional_id: int = 0x7DF
    extended_id: bool = False
    options: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return the YAML serialisable representation of the profile."""
        return {
            "name": self.name,
            "vci_type": self.vci_type.value,
            "channel": self.channel,
            "protocol": self.protocol.value,
            "bitrate": self.bitrate,
            "data_bitrate": self.data_bitrate,
            "tx_id": self.tx_id,
            "rx_id": self.rx_id,
            "functional_id": self.functional_id,
            "extended_id": self.extended_id,
            "options": dict(self.options),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConnectionProfile":
        """Build a profile from its serialised representation."""
        return cls(
            name=str(data.get("name", "Default")),
            vci_type=VCIType(str(data.get("vci_type", "VIRTUAL"))),
            channel=data.get("channel", 0),
            protocol=ProtocolType(str(data.get("protocol", "CAN"))),
            bitrate=int(data.get("bitrate", 500_000)),
            data_bitrate=int(data.get("data_bitrate", 2_000_000)),
            tx_id=int(data.get("tx_id", 0x7E0)),
            rx_id=int(data.get("rx_id", 0x7E8)),
            functional_id=int(data.get("functional_id", 0x7DF)),
            extended_id=bool(data.get("extended_id", False)),
            options=dict(data.get("options", {})),
        )

    @classmethod
    def from_config(cls, config: ConfigurationManager) -> "ConnectionProfile":
        """Build the profile described by the application configuration."""
        protocol = ProtocolType(str(config.get("connection.protocol", "CAN")))
        can_cfg = config.section("protocols.can")
        return cls(
            name="From configuration",
            vci_type=VCIType(str(config.get("connection.vci_type", "VIRTUAL"))),
            channel=config.get("connection.channel", 0),
            protocol=protocol,
            bitrate=int(can_cfg.get("bitrate", 500_000)),
            data_bitrate=int(config.get("protocols.can_fd.data_bitrate", 2_000_000)),
            tx_id=int(can_cfg.get("tx_id", 0x7E0)),
            rx_id=int(can_cfg.get("rx_id", 0x7E8)),
            functional_id=int(can_cfg.get("functional_id", 0x7DF)),
            extended_id=bool(can_cfg.get("extended_id", False)),
            options={
                "isotp": config.section("protocols.isotp"),
                "doip": config.section("protocols.doip"),
                "kline": config.section("protocols.kline"),
                "lin": config.section("protocols.lin"),
                "j1939": config.section("protocols.j1939"),
                "padding_enabled": can_cfg.get("padding_enabled", True),
                "padding_byte": can_cfg.get("padding_byte", 0x00),
            },
        )


class ConnectionManager:
    """Builds and supervises the VCI, protocol and transport stack."""

    def __init__(
        self,
        config: ConfigurationManager | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        """Create an idle manager."""
        self.config = config or get_config()
        self.bus = event_bus or get_event_bus()
        self.profile: ConnectionProfile = ConnectionProfile.from_config(self.config)
        self.driver: IVCIDriver | None = None
        self.protocol: IProtocolHandler | None = None
        self.transport: TransportLayer | None = None
        self._state = ConnectionState.DISCONNECTED
        self._lock = threading.RLock()
        self._health_timer: PeriodicTimer | None = None
        self._history: list[ConnectionProfile] = []

    # -- state --------------------------------------------------------------
    @property
    def state(self) -> ConnectionState:
        """Return the connection state of the whole stack."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Return ``True`` when diagnostics can be performed."""
        return self._state is ConnectionState.CONNECTED

    @property
    def history(self) -> list[ConnectionProfile]:
        """Return the most recently used profiles, newest first."""
        return list(self._history)

    # -- connect / disconnect -------------------------------------------------
    def connect(self, profile: ConnectionProfile | None = None) -> TransportLayer:
        """Build the stack described by *profile* and connect it.

        Returns:
            The ready to use :class:`TransportLayer`.

        Raises:
            ConnectionFailedError: Any layer failed to start.
        """
        with self._lock:
            if profile is not None:
                self.profile = profile
            self._set_state(ConnectionState.CONNECTING)
            try:
                self.driver = self._build_driver(self.profile)
                self.driver.connect()
                self.protocol = self._build_protocol(self.profile, self.driver)
                self.transport = TransportLayer(
                    self.protocol,
                    TransportTiming(
                        p2_client_ms=float(self.config.get("diagnostics.p2_client_ms", 150)),
                        p2_star_client_ms=float(
                            self.config.get("diagnostics.p2_star_client_ms", 5000)
                        ),
                        s3_client_ms=float(self.config.get("diagnostics.s3_client_ms", 4000)),
                    ),
                    self.bus,
                )
                self.transport.connect()
            except Exception as exc:  # noqa: BLE001 - normalise startup errors
                self._set_state(ConnectionState.ERROR)
                self._teardown()
                if isinstance(exc, ConnectionFailedError):
                    raise
                raise ConnectionFailedError(
                    "could not establish the diagnostic connection", {"cause": str(exc)}
                ) from exc
            self._remember(self.profile)
            self._set_state(ConnectionState.CONNECTED)
            self._start_health_checks()
            return self.transport

    def disconnect(self) -> None:
        """Tear the stack down; safe to call when already disconnected."""
        with self._lock:
            self._stop_health_checks()
            self._teardown()
            self._set_state(ConnectionState.DISCONNECTED)

    def reconnect(self) -> bool:
        """Disconnect and connect again with the current profile."""
        try:
            self.disconnect()
            self.connect(self.profile)
            return True
        except Exception:  # noqa: BLE001 - reported through the event bus
            _logger.exception("reconnect failed")
            return False

    # -- building blocks --------------------------------------------------------
    def _build_driver(self, profile: ConnectionProfile) -> IVCIDriver:
        """Instantiate and configure the VCI driver for *profile*."""
        driver = VCIFactory.create(profile.vci_type, event_bus=self.bus)
        driver.configure(
            VCIChannelConfig(
                channel=profile.channel,
                protocol=profile.protocol,
                bitrate=profile.bitrate,
                data_bitrate=profile.data_bitrate,
                serial_port=str(profile.options.get("kline", {}).get("port", "")),
                host=str(profile.options.get("doip", {}).get("host", "")),
                port=int(profile.options.get("doip", {}).get("port", 13400)),
            )
        )
        if bool(self.config.get("connection.auto_reconnect", True)):
            attempts = int(self.config.get("connection.reconnect_attempts", 3))
            delay = float(self.config.get("connection.reconnect_delay_ms", 1000)) / 1000.0
            enable = getattr(driver, "enable_auto_reconnect", None)
            if callable(enable):
                enable(attempts, delay)
        return driver

    def _build_protocol(self, profile: ConnectionProfile, driver: IVCIDriver) -> IProtocolHandler:
        """Instantiate the protocol handler for *profile*.

        Raises:
            UnsupportedProtocolError: The protocol has no handler.
        """
        common = {
            "tx_id": profile.tx_id,
            "rx_id": profile.rx_id,
            "functional_id": profile.functional_id,
            "extended_id": profile.extended_id,
            "padding_enabled": profile.options.get("padding_enabled", True),
            "padding_byte": profile.options.get("padding_byte", 0x00),
            "isotp": profile.options.get("isotp", {}),
        }
        if profile.protocol is ProtocolType.CAN:
            from .protocols.can.can_protocol import CANProtocol

            return CANProtocol(driver, common, self.bus)
        if profile.protocol is ProtocolType.CAN_FD:
            from .protocols.can.can_fd_protocol import CANFDProtocol

            return CANFDProtocol(
                driver, {**common, "data_bitrate": profile.data_bitrate}, self.bus
            )
        if profile.protocol is ProtocolType.DOIP:
            from .protocols.ethernet.doip_protocol import DoIPProtocol

            return DoIPProtocol(driver, {**common, **profile.options.get("doip", {})}, self.bus)
        if profile.protocol is ProtocolType.KLINE:
            from .protocols.kline.kline_protocol import KLineProtocol

            return KLineProtocol(driver, {**common, **profile.options.get("kline", {})}, self.bus)
        if profile.protocol is ProtocolType.LIN:
            from .protocols.lin.lin_protocol import LINProtocol

            return LINProtocol(driver, {**common, **profile.options.get("lin", {})}, self.bus)
        if profile.protocol is ProtocolType.J1939:
            from .protocols.j1939.j1939_protocol import J1939Protocol

            return J1939Protocol(driver, {**common, **profile.options.get("j1939", {})}, self.bus)
        if profile.protocol is ProtocolType.FLEXRAY:
            from .protocols.flexray.flexray_protocol import FlexRayProtocol

            return FlexRayProtocol(driver, common, self.bus)
        raise UnsupportedProtocolError(f"no handler for protocol {profile.protocol.value}")

    def _teardown(self) -> None:
        """Release the transport, protocol and driver in the right order."""
        if self.transport is not None:
            try:
                self.transport.disconnect()
            except Exception:  # noqa: BLE001
                _logger.debug("transport shutdown failed", exc_info=True)
            self.transport = None
        if self.protocol is not None:
            try:
                self.protocol.shutdown()
            except Exception:  # noqa: BLE001
                _logger.debug("protocol shutdown failed", exc_info=True)
            self.protocol = None
        if self.driver is not None:
            try:
                self.driver.disconnect()
            except Exception:  # noqa: BLE001
                _logger.debug("driver shutdown failed", exc_info=True)
            self.driver = None

    # -- health monitoring ----------------------------------------------------------
    def _start_health_checks(self) -> None:
        """Start the periodic connection health check."""
        interval_ms = float(self.config.get("connection.health_check_interval_ms", 5000))
        if interval_ms <= 0:
            return
        self._health_timer = PeriodicTimer(interval_ms / 1000.0, self._health_check, "conn-health")
        self._health_timer.start()

    def _stop_health_checks(self) -> None:
        """Stop the periodic connection health check."""
        if self._health_timer is not None:
            self._health_timer.stop()
            self._health_timer = None

    def _health_check(self) -> None:
        """Verify the driver is still usable, reconnecting when configured."""
        if self.driver is None or self.driver.is_connected:
            return
        _logger.warning("connection lost; attempting to recover")
        self.bus.publish(
            EventType.COMM_ERROR, {"reason": "connection lost"}, "ConnectionManager"
        )
        if bool(self.config.get("connection.auto_reconnect", True)):
            self.reconnect()

    # -- helpers ----------------------------------------------------------------------
    def _set_state(self, state: ConnectionState) -> None:
        """Update the state and publish the matching event."""
        if state == self._state:
            return
        self._state = state
        mapping = {
            ConnectionState.CONNECTING: EventType.COMM_CONNECTING,
            ConnectionState.CONNECTED: EventType.COMM_CONNECTED,
            ConnectionState.DISCONNECTED: EventType.COMM_DISCONNECTED,
            ConnectionState.ERROR: EventType.COMM_ERROR,
        }
        event = mapping.get(state)
        if event is not None:
            self.bus.publish(
                event,
                {
                    "state": state.value,
                    "profile": self.profile.name,
                    "protocol": self.profile.protocol.value,
                    "vci": self.profile.vci_type.value,
                },
                "ConnectionManager",
            )

    def _remember(self, profile: ConnectionProfile) -> None:
        """Insert *profile* at the front of the recent connections list."""
        self._history = [p for p in self._history if p.name != profile.name]
        self._history.insert(0, profile)
        del self._history[10:]

    def get_info(self) -> dict[str, Any]:
        """Return a mapping describing the whole stack for the status bar."""
        info: dict[str, Any] = {
            "state": self._state.value,
            "profile": self.profile.to_dict(),
        }
        if self.driver is not None:
            device = self.driver.get_device_info()
            info["device"] = {"name": device.name, "serial": device.serial_number}
            info["status"] = asdict(self.driver.get_status())
        if self.transport is not None:
            info["transport"] = self.transport.get_info()
        return info

    def __repr__(self) -> str:  # noqa: D105 - trivial
        return f"<ConnectionManager {self._state.value} {self.profile.protocol.value}>"


__all__ = ["ConnectionManager", "ConnectionProfile"]
