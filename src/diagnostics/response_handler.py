"""Response parsing, validation and caching."""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from ..core.enums.sid_enums import (
    NEGATIVE_RESPONSE_SID,
    POSITIVE_RESPONSE_OFFSET,
    ServiceID,
)
from ..core.exceptions import InvalidResponseError
from ..core.models.response_data_model import DiagnosticResponse
from .nrc_handler import NRCHandler

_logger = logging.getLogger(__name__)

#: Signature of a service specific parser.
ResponseParser = Callable[[DiagnosticResponse], Any]


@dataclass(slots=True)
class CacheEntry:
    """One cached response with its insertion timestamp."""

    response: DiagnosticResponse
    stored_at: float = field(default_factory=time.time)

    def is_fresh(self, ttl_s: float) -> bool:
        """Return ``True`` while the entry is younger than *ttl_s*."""
        return (time.time() - self.stored_at) <= ttl_s


class ResponseHandler:
    """Validates responses, decodes them and optionally caches them.

    Args:
        cache_enabled: Store positive responses for repeated identical requests.
        cache_ttl_s: Lifetime of a cache entry in seconds.
    """

    def __init__(self, cache_enabled: bool = False, cache_ttl_s: float = 2.0) -> None:
        """Create the handler."""
        self.cache_enabled = cache_enabled
        self.cache_ttl_s = cache_ttl_s
        self.nrc_handler = NRCHandler()
        self._parsers: dict[int, ResponseParser] = {}
        self._cache: dict[bytes, CacheEntry] = {}
        self._lock = threading.RLock()

    # -- validation ---------------------------------------------------------
    def validate(self, request: bytes, response: DiagnosticResponse) -> None:
        """Check the structural consistency of *response*.

        Raises:
            InvalidResponseError: The response echoes the wrong SID or a
                negative response is truncated.
        """
        if response.timed_out or not response.raw:
            return
        first = response.raw[0]
        if first == NEGATIVE_RESPONSE_SID:
            if len(response.raw) < 3:
                raise InvalidResponseError("truncated negative response")
            if request and response.raw[1] != request[0]:
                raise InvalidResponseError(
                    "the negative response references another service",
                    {"expected": f"0x{request[0]:02X}", "received": f"0x{response.raw[1]:02X}"},
                )
            return
        if request and first != (request[0] + POSITIVE_RESPONSE_OFFSET) & 0xFF:
            raise InvalidResponseError(
                "unexpected positive response identifier",
                {
                    "expected": f"0x{(request[0] + POSITIVE_RESPONSE_OFFSET) & 0xFF:02X}",
                    "received": f"0x{first:02X}",
                },
            )

    # -- decoding -------------------------------------------------------------
    def register_parser(self, service_id: int, parser: ResponseParser) -> None:
        """Register a service specific parser for *service_id*."""
        self._parsers[service_id] = parser

    def decode(self, response: DiagnosticResponse) -> Any:
        """Run the registered parser for the response, if any."""
        sid = response.request_sid
        if sid is None:
            return response
        parser = self._parsers.get(sid)
        return parser(response) if parser is not None else response

    def describe(self, response: DiagnosticResponse) -> str:
        """Return a human readable one line description of *response*."""
        if response.timed_out:
            return "timeout: the ECU did not answer"
        if response.suppressed and not response.raw:
            return "positive response suppressed by the tester"
        if response.is_negative:
            info = self.nrc_handler.describe(response.raw[2])
            return f"{info.summary} - {info.description}"
        sid = response.request_sid
        service = ServiceID.from_byte(sid) if sid is not None else None
        name = service.pretty_name if service else f"service 0x{sid:02X}" if sid else "response"
        return f"{name}: positive response with {len(response.data)} data bytes"

    def extract(self, response: DiagnosticResponse, start: int, length: int) -> bytes:
        """Return *length* bytes of the response payload starting at *start*."""
        return response.raw[start : start + length]

    # -- caching -----------------------------------------------------------------
    def cache_put(self, request: bytes, response: DiagnosticResponse) -> None:
        """Store a positive *response* for *request*."""
        if not self.cache_enabled or not response.is_positive():
            return
        with self._lock:
            self._cache[bytes(request)] = CacheEntry(response)

    def cache_get(self, request: bytes) -> DiagnosticResponse | None:
        """Return a fresh cached response for *request*, or ``None``."""
        if not self.cache_enabled:
            return None
        with self._lock:
            entry = self._cache.get(bytes(request))
            if entry is None:
                return None
            if not entry.is_fresh(self.cache_ttl_s):
                del self._cache[bytes(request)]
                return None
            return entry.response

    def cache_clear(self) -> None:
        """Empty the response cache."""
        with self._lock:
            self._cache.clear()

    @property
    def cache_size(self) -> int:
        """Return the number of cached responses."""
        with self._lock:
            return len(self._cache)


__all__ = ["ResponseHandler", "CacheEntry", "ResponseParser"]
