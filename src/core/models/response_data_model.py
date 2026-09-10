"""Model describing a parsed diagnostic response."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from ..enums.nrc_enums import NegativeResponseCode, describe_nrc
from ..enums.sid_enums import NEGATIVE_RESPONSE_SID, POSITIVE_RESPONSE_OFFSET


@dataclass(slots=True)
class DiagnosticResponse:
    """Result of a single UDS request/response exchange.

    Attributes:
        request: The raw request payload that was transmitted.
        raw: The raw response payload received from the ECU (may be empty on
            timeout or when the positive response was suppressed).
        timestamp: Unix timestamp when the response was received.
        elapsed_ms: Round trip time in milliseconds.
        timed_out: ``True`` when no response arrived within P2/P2*.
        suppressed: ``True`` when the positive response was intentionally
            suppressed by the client.
        pending_count: Number of ``0x78`` responsePending frames observed.
        metadata: Free-form context (channel, addressing, retries...).
    """

    request: bytes = b""
    raw: bytes = b""
    timestamp: float = field(default_factory=time.time)
    elapsed_ms: float = 0.0
    timed_out: bool = False
    suppressed: bool = False
    pending_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    # -- basic classification ------------------------------------------
    @property
    def request_sid(self) -> int | None:
        """Return the SID of the originating request."""
        return self.request[0] if self.request else None

    @property
    def is_negative(self) -> bool:
        """Return ``True`` for a ``0x7F`` negative response."""
        return len(self.raw) >= 3 and self.raw[0] == NEGATIVE_RESPONSE_SID

    def is_positive(self) -> bool:
        """Return ``True`` when the ECU accepted the request.

        A suppressed positive response also counts as positive, since the ECU
        was explicitly asked not to answer.
        """
        if self.suppressed and not self.raw:
            return True
        if self.timed_out or not self.raw:
            return False
        if self.is_negative:
            return False
        if self.request_sid is None:
            return True
        return self.raw[0] == (self.request_sid + POSITIVE_RESPONSE_OFFSET) & 0xFF

    @property
    def nrc(self) -> int | None:
        """Return the negative response code, or ``None`` if positive."""
        return self.raw[2] if self.is_negative else None

    @property
    def nrc_enum(self) -> NegativeResponseCode | None:
        """Return the :class:`NegativeResponseCode` when applicable."""
        code = self.nrc
        return None if code is None else NegativeResponseCode.from_byte(code)

    @property
    def nrc_text(self) -> str:
        """Return a readable description of the NRC, or an empty string."""
        code = self.nrc
        return "" if code is None else describe_nrc(code)

    # -- payload access --------------------------------------------------
    @property
    def data(self) -> bytes:
        """Return the response payload without the echoed service identifier."""
        if self.is_negative or not self.raw:
            return b""
        return self.raw[1:]

    @property
    def hex_raw(self) -> str:
        """Return the raw response as space separated uppercase hex."""
        return " ".join(f"{b:02X}" for b in self.raw)

    def slice_bytes(self, start: int, length: int) -> bytes:
        """Return ``length`` bytes of :attr:`raw` starting at *start*."""
        return self.raw[start : start + length]

    def summary(self) -> str:
        """Return a one line description suitable for logs and tables."""
        if self.timed_out:
            return f"TIMEOUT after {self.elapsed_ms:.1f} ms"
        if self.suppressed and not self.raw:
            return "positive response suppressed"
        if self.is_negative:
            return self.nrc_text
        return f"positive response ({len(self.raw)} bytes) in {self.elapsed_ms:.1f} ms"

    def __bool__(self) -> bool:  # noqa: D105 - trivial
        return self.is_positive()


__all__ = ["DiagnosticResponse"]
