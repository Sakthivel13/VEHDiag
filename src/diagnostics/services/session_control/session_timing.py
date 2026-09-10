"""P2 / P2* / S3 timing helpers for diagnostic sessions."""
from __future__ import annotations

from dataclasses import dataclass

from ....core.models.session_model import SessionTiming

#: Resolution of the P2* value inside a 0x50 response, in milliseconds.
P2_STAR_RESOLUTION_MS = 10.0

#: Default S3 server time defined by ISO 14229-2.
DEFAULT_S3_SERVER_MS = 5000.0


@dataclass(slots=True)
class TimingBudget:
    """Client side timing derived from the server values.

    Attributes:
        p2_server_ms: P2 reported by the ECU.
        p2_star_server_ms: P2* reported by the ECU.
        safety_factor: Multiplier applied to obtain the client timeouts.
        tester_present_ratio: Fraction of S3 used as the keep-alive interval.
    """

    p2_server_ms: float = 50.0
    p2_star_server_ms: float = 5000.0
    safety_factor: float = 1.5
    tester_present_ratio: float = 0.5

    @property
    def p2_client_ms(self) -> float:
        """Return the client timeout for the first response."""
        return max(50.0, self.p2_server_ms * self.safety_factor)

    @property
    def p2_star_client_ms(self) -> float:
        """Return the client timeout applied after a pending response."""
        return max(1000.0, self.p2_star_server_ms * self.safety_factor)

    def tester_present_interval_ms(self, s3_server_ms: float = DEFAULT_S3_SERVER_MS) -> float:
        """Return the recommended TesterPresent interval."""
        return max(500.0, s3_server_ms * self.tester_present_ratio)

    @classmethod
    def from_session_timing(cls, timing: SessionTiming) -> "TimingBudget":
        """Build a budget from the values reported in a 0x50 response."""
        return cls(p2_server_ms=timing.p2_server_ms, p2_star_server_ms=timing.p2_star_server_ms)


def parse_timing_bytes(data: bytes) -> SessionTiming:
    """Parse the four timing bytes of a DiagnosticSessionControl response.

    Example:
        >>> t = parse_timing_bytes(bytes.fromhex("003201F4"))
        >>> t.p2_server_ms, t.p2_star_server_ms
        (50.0, 5000.0)
    """
    return SessionTiming.from_response(data)


def encode_timing_bytes(p2_ms: float, p2_star_ms: float) -> bytes:
    """Encode P2/P2* into the four response bytes (used by simulators).

    Example:
        >>> encode_timing_bytes(50, 5000).hex().upper()
        '003201F4'
    """
    p2 = int(round(p2_ms)) & 0xFFFF
    p2_star = int(round(p2_star_ms / P2_STAR_RESOLUTION_MS)) & 0xFFFF
    return p2.to_bytes(2, "big") + p2_star.to_bytes(2, "big")


__all__ = [
    "TimingBudget",
    "parse_timing_bytes",
    "encode_timing_bytes",
    "P2_STAR_RESOLUTION_MS",
    "DEFAULT_S3_SERVER_MS",
]
