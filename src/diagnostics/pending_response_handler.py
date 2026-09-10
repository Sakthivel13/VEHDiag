"""Handling of the ``0x78`` requestCorrectlyReceivedResponsePending NRC."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable

from ..core.enums.nrc_enums import NegativeResponseCode
from ..core.enums.sid_enums import NEGATIVE_RESPONSE_SID

_logger = logging.getLogger(__name__)

#: The NRC value meaning "response pending".
RESPONSE_PENDING = int(NegativeResponseCode.REQUEST_CORRECTLY_RECEIVED_RESPONSE_PENDING)


def is_pending(payload: bytes) -> bool:
    """Return ``True`` when *payload* is a ``0x7F xx 0x78`` response.

    Example:
        >>> is_pending(bytes.fromhex("7F2278"))
        True
        >>> is_pending(bytes.fromhex("62F190"))
        False
    """
    return len(payload) >= 3 and payload[0] == NEGATIVE_RESPONSE_SID and payload[2] == RESPONSE_PENDING


@dataclass(slots=True)
class PendingStatistics:
    """Counters describing one pending-response wait."""

    count: int = 0
    total_wait_ms: float = 0.0
    max_wait_ms: float = 0.0

    def record(self, wait_ms: float) -> None:
        """Record one pending response that waited *wait_ms* milliseconds."""
        self.count += 1
        self.total_wait_ms += wait_ms
        self.max_wait_ms = max(self.max_wait_ms, wait_ms)


class PendingResponseHandler:
    """Keeps reading responses while the ECU answers ``0x78``.

    Args:
        p2_star_ms: Timeout applied after each pending response.
        max_pending: Maximum number of consecutive pending responses accepted.
        on_pending: Optional callback invoked with the pending count, used to
            drive a progress indicator in the UI.
    """

    def __init__(
        self,
        p2_star_ms: float = 5000.0,
        max_pending: int = 20,
        on_pending: Callable[[int], None] | None = None,
    ) -> None:
        """Create the handler."""
        self.p2_star_ms = p2_star_ms
        self.max_pending = max_pending
        self.on_pending = on_pending
        self.statistics = PendingStatistics()

    def resolve(
        self,
        first_response: bytes | None,
        receive: Callable[[float], bytes | None],
    ) -> tuple[bytes | None, int]:
        """Return the final response after consuming pending frames.

        Args:
            first_response: The response already received, possibly ``0x78``.
            receive: Callable returning the next response payload.

        Returns:
            Tuple of the final payload (or ``None`` on timeout) and the number
            of pending responses that were consumed.
        """
        response = first_response
        pending_count = 0
        while response is not None and is_pending(response):
            pending_count += 1
            if pending_count > self.max_pending:
                _logger.warning("ECU exceeded %d pending responses", self.max_pending)
                return response, pending_count
            if self.on_pending is not None:
                self.on_pending(pending_count)
            started = time.perf_counter()
            response = receive(self.p2_star_ms / 1000.0)
            self.statistics.record((time.perf_counter() - started) * 1000.0)
        return response, pending_count

    def reset(self) -> None:
        """Clear the accumulated statistics."""
        self.statistics = PendingStatistics()


__all__ = ["PendingResponseHandler", "PendingStatistics", "is_pending", "RESPONSE_PENDING"]
