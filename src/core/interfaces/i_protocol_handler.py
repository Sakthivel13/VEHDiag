"""Abstract protocol handler interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..enums.protocol_enums import ProtocolType


class IProtocolHandler(ABC):
    """Contract implemented by every transport/network layer protocol.

    A protocol handler sits between the raw :class:`IVCIDriver` frames and the
    diagnostic layer. It is responsible for segmentation, reassembly, framing
    and protocol specific timing.
    """

    @property
    @abstractmethod
    def protocol_type(self) -> ProtocolType:
        """Return the protocol implemented by this handler."""

    @abstractmethod
    def initialize(self) -> None:
        """Perform any protocol level handshake (init sequences, routing...).

        Raises:
            ProtocolError: The initialisation handshake failed.
        """

    @abstractmethod
    def shutdown(self) -> None:
        """Release protocol resources and stop background activity."""

    @abstractmethod
    def send_message(self, payload: bytes, functional: bool = False) -> None:
        """Send an assembled diagnostic payload.

        Args:
            payload: Complete UDS payload starting with the SID.
            functional: Use functional (broadcast) addressing.
        """

    @abstractmethod
    def receive_message(self, timeout: float = 1.0) -> bytes | None:
        """Return the next assembled payload, or ``None`` on timeout.

        Args:
            timeout: Maximum time to block, in seconds.
        """

    @abstractmethod
    def set_timing(self, **timings: float) -> None:
        """Update protocol timing parameters (P2, P2*, STmin, ...)."""

    @abstractmethod
    def get_protocol_info(self) -> dict[str, Any]:
        """Return a mapping describing the current protocol configuration."""


__all__ = ["IProtocolHandler"]
