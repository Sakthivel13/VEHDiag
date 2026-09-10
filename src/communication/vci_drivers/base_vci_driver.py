"""Base implementation shared by every VCI driver.

The class implements the template method pattern: :meth:`connect` and
:meth:`disconnect` handle state transitions, statistics and event publication,
while subclasses only implement the vendor specific ``_do_*`` hooks.
"""
from __future__ import annotations

import logging
import threading
import time
from abc import abstractmethod

from ...core.enums.protocol_enums import MessageDirection
from ...core.enums.vci_enums import VCICapability, VCIState, VCIType
from ...core.event_bus import EventBus, EventType, get_event_bus
from ...core.exceptions import ConnectionFailedError, NotConnectedError
from ...core.interfaces.i_vci_driver import IVCIDriver
from ...core.models.message_model import BusMessage
from ...core.models.vci_model import VCIChannelConfig, VCIDeviceInfo, VCIStatus

_logger = logging.getLogger(__name__)


class BaseVCIDriver(IVCIDriver):
    """Common behaviour for all VCI drivers.

    Subclasses must implement :meth:`_do_connect`, :meth:`_do_disconnect`,
    :meth:`_do_send`, :meth:`_do_receive` and :meth:`_build_device_info`.
    """

    #: Hardware family implemented by the subclass.
    vci_type: VCIType = VCIType.VIRTUAL
    #: Features the driver advertises to the connection panel.
    capabilities: frozenset[VCICapability] = frozenset({VCICapability.CAN})

    def __init__(
        self,
        config: VCIChannelConfig | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        """Create the driver in the ``UNINITIALIZED`` state."""
        self.config = config or VCIChannelConfig()
        self.bus = event_bus or get_event_bus()
        self.status = VCIStatus(state=VCIState.UNINITIALIZED)
        self._lock = threading.RLock()
        self._connected_at: float = 0.0
        self._auto_reconnect = False
        self._reconnect_attempts = 3
        self._reconnect_delay_s = 1.0

    # -- template methods ---------------------------------------------------
    def configure(self, config: VCIChannelConfig) -> None:
        """Store *config*; it is applied on the next :meth:`connect`."""
        with self._lock:
            self.config = config
            if self.status.state is VCIState.UNINITIALIZED:
                self.status.state = VCIState.INITIALIZED

    def connect(self) -> None:
        """Open the channel, publishing the appropriate events.

        Raises:
            ConnectionFailedError: The vendor driver refused to open the channel.
        """
        with self._lock:
            if self.status.state is VCIState.CONNECTED:
                return
            self.bus.publish(
                EventType.COMM_CONNECTING,
                {"vci": self.vci_type.value, "channel": self.config.channel},
                type(self).__name__,
            )
            try:
                self._do_connect()
            except Exception as exc:  # noqa: BLE001 - normalise driver errors
                self.status.state = VCIState.ERROR
                self.status.last_error = str(exc)
                self.bus.publish(
                    EventType.COMM_ERROR,
                    {"vci": self.vci_type.value, "error": str(exc)},
                    type(self).__name__,
                )
                if isinstance(exc, ConnectionFailedError):
                    raise
                raise ConnectionFailedError(
                    f"failed to open {self.vci_type.display_name}", {"cause": str(exc)}
                ) from exc
            self.status.state = VCIState.CONNECTED
            self.status.last_error = ""
            self._connected_at = time.time()
            self.bus.publish(
                EventType.COMM_CONNECTED,
                {"vci": self.vci_type.value, "channel": self.config.channel},
                type(self).__name__,
            )
            _logger.info("%s connected on channel %s", self.vci_type.value, self.config.channel)

    def disconnect(self) -> None:
        """Close the channel; safe to call when already disconnected."""
        with self._lock:
            if self.status.state is not VCIState.CONNECTED:
                self.status.state = VCIState.DISCONNECTED
                return
            try:
                self._do_disconnect()
            except Exception:  # noqa: BLE001 - never fail on shutdown
                _logger.exception("error while disconnecting %s", self.vci_type.value)
            self.status.state = VCIState.DISCONNECTED
            self.bus.publish(
                EventType.COMM_DISCONNECTED,
                {"vci": self.vci_type.value},
                type(self).__name__,
            )

    def send(self, message: BusMessage) -> None:
        """Transmit *message* and update the statistics.

        Raises:
            NotConnectedError: The channel is not open.
        """
        if self.status.state is not VCIState.CONNECTED:
            raise NotConnectedError(
                f"{self.vci_type.display_name} is not connected",
                {"state": self.status.state.value},
            )
        message.direction = MessageDirection.TX
        if not message.channel:
            message.channel = str(self.config.channel)
        self._do_send(message)
        self.status.tx_count += 1

    def receive(self, timeout: float = 1.0) -> BusMessage | None:
        """Return the next received frame or ``None`` on timeout."""
        if self.status.state is not VCIState.CONNECTED:
            return None
        message = self._do_receive(timeout)
        if message is not None:
            message.direction = MessageDirection.RX
            if not message.channel:
                message.channel = str(self.config.channel)
            self.status.rx_count += 1
        return message

    def get_status(self) -> VCIStatus:
        """Return the live channel status."""
        return self.status

    def get_device_info(self) -> VCIDeviceInfo:
        """Return static hardware information."""
        info = self._build_device_info()
        info.capabilities = set(self.capabilities)
        return info

    # -- reconnection ---------------------------------------------------------
    def enable_auto_reconnect(self, attempts: int = 3, delay_s: float = 1.0) -> None:
        """Enable automatic reconnection attempts after a connection loss."""
        self._auto_reconnect = True
        self._reconnect_attempts = attempts
        self._reconnect_delay_s = delay_s

    def try_reconnect(self) -> bool:
        """Attempt to reconnect using the configured retry policy."""
        if not self._auto_reconnect:
            return False
        for attempt in range(1, self._reconnect_attempts + 1):
            _logger.info("reconnect attempt %d/%d", attempt, self._reconnect_attempts)
            try:
                self.disconnect()
                self.connect()
                return True
            except Exception:  # noqa: BLE001
                time.sleep(self._reconnect_delay_s * attempt)
        return False

    @property
    def uptime_s(self) -> float:
        """Return how long the channel has been open, in seconds."""
        return time.time() - self._connected_at if self._connected_at else 0.0

    def supports(self, capability: VCICapability) -> bool:
        """Return ``True`` when the driver advertises *capability*."""
        return capability in self.capabilities

    # -- hooks implemented by subclasses -----------------------------------------
    @abstractmethod
    def _do_connect(self) -> None:
        """Open the vendor channel."""

    @abstractmethod
    def _do_disconnect(self) -> None:
        """Close the vendor channel."""

    @abstractmethod
    def _do_send(self, message: BusMessage) -> None:
        """Hand one frame to the vendor library."""

    @abstractmethod
    def _do_receive(self, timeout: float) -> BusMessage | None:
        """Read one frame from the vendor library."""

    @abstractmethod
    def _build_device_info(self) -> VCIDeviceInfo:
        """Return static information about the hardware."""

    def __repr__(self) -> str:  # noqa: D105 - trivial
        return f"<{type(self).__name__} {self.vci_type.value} {self.status.state.value}>"


__all__ = ["BaseVCIDriver"]
