"""Base class shared by every protocol handler."""
from __future__ import annotations

import logging
import threading
from abc import abstractmethod
from typing import Any

from ...core.enums.protocol_enums import ConnectionState, ProtocolType
from ...core.event_bus import EventBus, EventType, get_event_bus
from ...core.exceptions import NotConnectedError
from ...core.interfaces.i_protocol_handler import IProtocolHandler
from ...core.interfaces.i_vci_driver import IVCIDriver

_logger = logging.getLogger(__name__)


class BaseProtocol(IProtocolHandler):
    """Common behaviour for all protocol handlers.

    Subclasses implement :meth:`initialize`, :meth:`send_message` and
    :meth:`receive_message`; this class provides state handling, event bus
    notification, timing storage and driver access.
    """

    def __init__(
        self,
        driver: IVCIDriver,
        config: dict[str, Any] | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        """Store the driver and configuration.

        Args:
            driver: The VCI driver used to move raw frames.
            config: Protocol specific configuration mapping.
            event_bus: Bus used for communication notifications.
        """
        self.driver = driver
        self.config: dict[str, Any] = dict(config or {})
        self.bus = event_bus or get_event_bus()
        self._state = ConnectionState.DISCONNECTED
        self._lock = threading.RLock()
        self._timings: dict[str, float] = {}

    # -- state -------------------------------------------------------------
    @property
    def state(self) -> ConnectionState:
        """Return the connection state of the protocol handler."""
        return self._state

    def _set_state(self, state: ConnectionState) -> None:
        """Change the state and publish the matching event."""
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
                {"protocol": self.protocol_type.value, "state": state.value},
                type(self).__name__,
            )

    @property
    def is_connected(self) -> bool:
        """Return ``True`` when the handler is ready to exchange messages."""
        return self._state is ConnectionState.CONNECTED

    def _require_connection(self) -> None:
        """Raise when the handler is not connected.

        Raises:
            NotConnectedError: The protocol has not been initialised.
        """
        if not self.is_connected:
            raise NotConnectedError(
                f"{self.protocol_type.value} protocol is not connected",
                {"state": self._state.value},
            )

    # -- interface defaults ------------------------------------------------------
    @property
    @abstractmethod
    def protocol_type(self) -> ProtocolType:
        """Return the protocol implemented by the subclass."""

    def shutdown(self) -> None:
        """Default shutdown: mark the handler disconnected."""
        self._set_state(ConnectionState.DISCONNECTED)

    def set_timing(self, **timings: float) -> None:
        """Store protocol timing parameters."""
        with self._lock:
            self._timings.update({k: float(v) for k, v in timings.items()})

    def get_timing(self, name: str, default: float = 0.0) -> float:
        """Return one stored timing parameter."""
        return self._timings.get(name, default)

    def get_protocol_info(self) -> dict[str, Any]:
        """Return a mapping describing the current configuration."""
        return {
            "protocol": self.protocol_type.value,
            "state": self._state.value,
            "timings": dict(self._timings),
            "config": dict(self.config),
        }

    def __repr__(self) -> str:  # noqa: D105 - trivial
        return f"<{type(self).__name__} {self.protocol_type.value} {self._state.value}>"


__all__ = ["BaseProtocol"]
