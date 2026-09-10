"""K-Line timing parameters (ISO 9141-2 / ISO 14230-2)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class KLineTiming:
    """Inter-byte and inter-message timing for K-Line communication.

    Attributes:
        p1_ms: Inter-byte time within an ECU response.
        p2_ms: Time between a tester request and the ECU response.
        p3_ms: Time between the end of a response and the next request.
        p4_ms: Inter-byte time within a tester request.
        w1_ms: Time from the end of the address byte to the sync pattern.
        w2_ms: Time from the sync pattern to the first key byte.
        w3_ms: Time between the two key bytes.
        w4_ms: Time from the second key byte to its inverted echo.
        w5_ms: Idle bus time required before a new 5-baud init.
    """

    p1_ms: float = 5.0
    p2_ms: float = 50.0
    p3_ms: float = 55.0
    p4_ms: float = 5.0
    w1_ms: float = 300.0
    w2_ms: float = 20.0
    w3_ms: float = 20.0
    w4_ms: float = 50.0
    w5_ms: float = 300.0

    @classmethod
    def iso9141(cls) -> "KLineTiming":
        """Return the timing recommended by ISO 9141-2."""
        return cls(p1_ms=5, p2_ms=50, p3_ms=55, p4_ms=5)

    @classmethod
    def kwp2000_fast(cls) -> "KLineTiming":
        """Return the timing recommended for KWP2000 fast initialisation."""
        return cls(p1_ms=0, p2_ms=25, p3_ms=55, p4_ms=5)

    def byte_timeout_s(self) -> float:
        """Return the serial read timeout to use between response bytes."""
        return max(0.02, self.p1_ms * 4 / 1000.0)

    def response_timeout_s(self) -> float:
        """Return the timeout to wait for the first response byte."""
        return max(0.1, self.p2_ms * 20 / 1000.0)


#: Fast initialisation low/high pulse durations in milliseconds.
FAST_INIT_LOW_MS = 25.0
FAST_INIT_HIGH_MS = 25.0

#: Duration of one bit at 5 baud, in milliseconds.
FIVE_BAUD_BIT_MS = 200.0


__all__ = ["KLineTiming", "FAST_INIT_LOW_MS", "FAST_INIT_HIGH_MS", "FIVE_BAUD_BIT_MS"]
