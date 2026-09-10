"""Diagnostic session state machine."""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Callable

from ..utils.timer_utils import PeriodicTimer
from .enums.session_enums import SecurityState, SessionType, session_name
from .event_bus import EventBus, EventType, get_event_bus
from .models.session_model import SessionState, SessionTiming, SessionTransition

_logger = logging.getLogger(__name__)

#: Transitions the ECU normally accepts, keyed by the current session.
ALLOWED_TRANSITIONS: dict[int, set[int]] = {
    int(SessionType.DEFAULT): {0x01, 0x02, 0x03, 0x04},
    int(SessionType.PROGRAMMING): {0x01, 0x02, 0x03},
    int(SessionType.EXTENDED_DIAGNOSTIC): {0x01, 0x02, 0x03, 0x04},
    int(SessionType.SAFETY_SYSTEM_DIAGNOSTIC): {0x01, 0x03, 0x04},
}


class SessionManager:
    """Tracks the active diagnostic session and the S3 timeout.

    Args:
        event_bus: Shared event bus.
        on_timeout: Callback invoked when the S3 timer expires.

    Example:
        >>> manager = SessionManager()
        >>> manager.apply_change(0x03)
        True
        >>> manager.state.session_label
        'extendedDiagnosticSession'
        >>> manager.requires_tester_present
        True
        >>> manager.reset()
        >>> manager.state.active_session
        1
    """

    def __init__(
        self,
        event_bus: EventBus | None = None,
        on_timeout: Callable[[], None] | None = None,
    ) -> None:
        """Create the manager in the default session."""
        self.bus = event_bus or get_event_bus()
        self.on_timeout = on_timeout
        self.state = SessionState()
        self._lock = threading.RLock()
        self._watchdog: PeriodicTimer | None = None

    # -- state ---------------------------------------------------------------
    @property
    def active_session(self) -> int:
        """Return the active session sub-function."""
        return self.state.active_session

    @property
    def requires_tester_present(self) -> bool:
        """Return ``True`` when the session must be kept alive."""
        return self.state.requires_tester_present

    @property
    def is_unlocked(self) -> bool:
        """Return ``True`` when a security level is unlocked."""
        return self.state.security_state is SecurityState.UNLOCKED

    def can_transition_to(self, session: int) -> bool:
        """Return ``True`` when the transition is normally permitted."""
        allowed = ALLOWED_TRANSITIONS.get(self.state.active_session)
        return True if allowed is None else session in allowed or session >= 0x40

    # -- transitions ----------------------------------------------------------
    def apply_change(self, session: int, timing: SessionTiming | None = None) -> bool:
        """Record a successful session change.

        Returns:
            ``True`` when the transition was applied.
        """
        with self._lock:
            previous = self.state.active_session
            self.state.apply_session(session, timing)
        self.bus.publish(
            EventType.DIAG_SESSION_CHANGED,
            {"from": previous, "session": session, "label": session_name(session)},
            "SessionManager",
        )
        _logger.info("session %s -> %s", session_name(previous), session_name(session))
        self._restart_watchdog()
        return True

    def apply_unlock(self, level: int) -> None:
        """Record a successful security unlock."""
        with self._lock:
            self.state.apply_unlock(level)
        self.bus.publish(EventType.DIAG_SECURITY_UNLOCKED, {"level": level}, "SessionManager")

    def touch(self) -> None:
        """Reset the S3 inactivity timer after any diagnostic activity."""
        self.state.touch()

    def reset(self) -> None:
        """Return to the default session and lock security."""
        with self._lock:
            self.state.reset()
        self.stop_watchdog()
        self.bus.publish(
            EventType.DIAG_SESSION_CHANGED,
            {"session": int(SessionType.DEFAULT), "label": "defaultSession"},
            "SessionManager",
        )

    @property
    def history(self) -> list[SessionTransition]:
        """Return the recorded session transitions."""
        return list(self.state.history)

    # -- watchdog --------------------------------------------------------------
    def start_watchdog(self, interval_s: float = 0.5) -> None:
        """Start monitoring the S3 timeout."""
        if self._watchdog is not None:
            return
        self._watchdog = PeriodicTimer(interval_s, self._check_timeout, "session-watchdog")
        self._watchdog.start()

    def stop_watchdog(self) -> None:
        """Stop monitoring the S3 timeout."""
        if self._watchdog is not None:
            self._watchdog.stop()
            self._watchdog = None

    def _restart_watchdog(self) -> None:
        """Start or stop the watchdog according to the active session."""
        if self.requires_tester_present:
            self.start_watchdog()
        else:
            self.stop_watchdog()

    def _check_timeout(self) -> None:
        """Fall back to the default session when S3 expired."""
        if not self.requires_tester_present:
            return
        if self.state.s3_remaining_ms > 0:
            return
        _logger.warning("S3 timeout expired; the ECU returned to the default session")
        self.reset()
        if self.on_timeout is not None:
            self.on_timeout()


__all__ = ["SessionManager", "ALLOWED_TRANSITIONS"]
