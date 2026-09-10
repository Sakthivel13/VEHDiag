"""Diagnostic session state model."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from ..enums.session_enums import SecurityState, SessionType, session_name


@dataclass(slots=True)
class SessionTiming:
    """P2/P2* server timing values negotiated with the ECU."""

    p2_server_ms: float = 50.0
    p2_star_server_ms: float = 5000.0
    s3_client_ms: float = 4000.0

    @classmethod
    def from_response(cls, data: bytes) -> "SessionTiming":
        """Parse the four timing bytes of a 0x50 positive response.

        Args:
            data: Response payload after the session echo, i.e. four bytes
                ``P2_HI P2_LO P2STAR_HI P2STAR_LO``.

        Returns:
            Parsed timing values; defaults are kept when *data* is too short.
        """
        if len(data) < 4:
            return cls()
        p2 = int.from_bytes(data[0:2], "big")
        p2_star = int.from_bytes(data[2:4], "big") * 10  # resolution is 10 ms
        return cls(p2_server_ms=float(p2), p2_star_server_ms=float(p2_star))


@dataclass(slots=True)
class SessionTransition:
    """A recorded change of the active diagnostic session."""

    from_session: int
    to_session: int
    timestamp: float = field(default_factory=time.time)
    successful: bool = True

    def __str__(self) -> str:  # noqa: D105 - trivial
        arrow = "->" if self.successful else "-x"
        return f"{session_name(self.from_session)} {arrow} {session_name(self.to_session)}"


@dataclass(slots=True)
class SessionState:
    """Current diagnostic state of the connected ECU."""

    active_session: int = int(SessionType.DEFAULT)
    timing: SessionTiming = field(default_factory=SessionTiming)
    security_state: SecurityState = SecurityState.LOCKED
    unlocked_level: int | None = None
    last_activity: float = field(default_factory=time.time)
    history: list[SessionTransition] = field(default_factory=list)

    @property
    def session_label(self) -> str:
        """Return the readable name of the active session."""
        return session_name(self.active_session)

    @property
    def requires_tester_present(self) -> bool:
        """Return ``True`` when the session must be kept alive."""
        return self.active_session != int(SessionType.DEFAULT)

    @property
    def seconds_since_activity(self) -> float:
        """Return the elapsed time since the last diagnostic request."""
        return time.time() - self.last_activity

    @property
    def s3_remaining_ms(self) -> float:
        """Return the remaining S3 time before the session times out."""
        remaining = self.timing.s3_client_ms - self.seconds_since_activity * 1000.0
        return max(0.0, remaining)

    def touch(self) -> None:
        """Reset the S3 inactivity timer."""
        self.last_activity = time.time()

    def apply_session(self, new_session: int, timing: SessionTiming | None = None) -> None:
        """Record a successful transition to *new_session*."""
        self.history.append(SessionTransition(self.active_session, new_session, successful=True))
        self.active_session = new_session
        if timing is not None:
            timing.s3_client_ms = self.timing.s3_client_ms
            self.timing = timing
        if new_session == int(SessionType.DEFAULT):
            self.security_state = SecurityState.LOCKED
            self.unlocked_level = None
        self.touch()

    def apply_unlock(self, level: int) -> None:
        """Record a successful security unlock for *level*."""
        self.security_state = SecurityState.UNLOCKED
        self.unlocked_level = level
        self.touch()

    def reset(self) -> None:
        """Return to the default session and lock security."""
        self.apply_session(int(SessionType.DEFAULT))


__all__ = ["SessionTiming", "SessionTransition", "SessionState"]
