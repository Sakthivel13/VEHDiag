"""Availability rules for the diagnostic service tabs.

A service tab is only usable when the transport is connected, when the active
session allows the service and, for the protected services, when security
access has been granted. This module turns those rules into a small, pure
state machine that :class:`~ui.panels.diagnostic_panel.DiagnosticMainPanel`
and the diagnostic controller both use.

Example:
    >>> from ui.panels.diagnostic_panel.service_tab_manager import (
    ...     TabState, TAB_SERVICES, evaluate_tab)
    >>> TAB_SERVICES["Read DTC"]
    25
    >>> state = evaluate_tab("Security", connected=False, session=1, unlocked=False)
    >>> state.enabled, state.reason
    (False, 'Connect to a VCI first')
    >>> evaluate_tab("Session", connected=True, session=1, unlocked=False).enabled
    True
    >>> evaluate_tab("Flash / transfer", connected=True, session=3, unlocked=False).reason
    'Requires security access'
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from PySide6.QtCore import QObject, Signal

from src.core.enums.session_enums import SessionType
from src.core.enums.sid_enums import (
    NON_DEFAULT_SESSION_SERVICES,
    SECURITY_REQUIRED_SERVICES,
    ServiceID,
)

__all__ = [
    "TAB_ICONS",
    "TAB_SERVICES",
    "ServiceTabManager",
    "TabState",
    "evaluate_tab",
    "evaluate_tabs",
]

#: Primary service identifier behind each diagnostic tab.
TAB_SERVICES: dict[str, int] = {
    "Session": int(ServiceID.DIAGNOSTIC_SESSION_CONTROL),
    "Read DID": int(ServiceID.READ_DATA_BY_IDENTIFIER),
    "Read DTC": int(ServiceID.READ_DTC_INFORMATION),
    "Clear DTC": int(ServiceID.CLEAR_DIAGNOSTIC_INFORMATION),
    "Security": int(ServiceID.SECURITY_ACCESS),
    "I/O control": int(ServiceID.INPUT_OUTPUT_CONTROL_BY_IDENTIFIER),
    "Routine": int(ServiceID.ROUTINE_CONTROL),
    "Flash / transfer": int(ServiceID.REQUEST_DOWNLOAD),
    "Tester present": int(ServiceID.TESTER_PRESENT),
    "Raw request": 0,
}

#: Icon name used for each tab.
TAB_ICONS: dict[str, str] = {
    "Session": "play",
    "Read DID": "search",
    "Read DTC": "dtc",
    "Clear DTC": "clear",
    "Security": "plugin",
    "I/O control": "settings",
    "Routine": "run_all",
    "Flash / transfer": "flash",
    "Tester present": "refresh",
    "Raw request": "file_hex",
}


@dataclass(frozen=True, slots=True)
class TabState:
    """Whether a tab may be used and why not.

    Attributes:
        title: The tab title.
        enabled: ``True`` when the operator may interact with the tab.
        reason: Explanation shown as a tooltip when :attr:`enabled` is false.
    """

    title: str
    enabled: bool
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        """Return the state as a plain mapping.

        Example:
            >>> TabState("Session", True).as_dict()["enabled"]
            True
        """
        return {"title": self.title, "enabled": self.enabled, "reason": self.reason}


def evaluate_tab(
    title: str,
    connected: bool,
    session: int = int(SessionType.DEFAULT),
    unlocked: bool = False,
) -> TabState:
    """Return the :class:`TabState` of the tab *title*.

    Args:
        title: The tab title, a key of :data:`TAB_SERVICES`.
        connected: Whether the transport is connected.
        session: The active diagnostic session sub-function.
        unlocked: Whether security access has been granted.

    Returns:
        The evaluated state.

    Example:
        >>> evaluate_tab("I/O control", connected=True, session=1).reason
        'Requires a non-default session'
        >>> evaluate_tab("Clear DTC", connected=True, session=1).enabled
        True
    """
    if not connected:
        return TabState(title, False, "Connect to a VCI first")
    service = TAB_SERVICES.get(title, 0)
    if service and service in SECURITY_REQUIRED_SERVICES and not unlocked:
        return TabState(title, False, "Requires security access")
    if (
        service
        and service in NON_DEFAULT_SESSION_SERVICES
        and session == int(SessionType.DEFAULT)
    ):
        return TabState(title, False, "Requires a non-default session")
    return TabState(title, True, "")


def evaluate_tabs(
    titles: Iterable[str],
    connected: bool,
    session: int = int(SessionType.DEFAULT),
    unlocked: bool = False,
) -> dict[str, TabState]:
    """Evaluate every tab of *titles*.

    Example:
        >>> states = evaluate_tabs(["Session", "Security"], connected=True)
        >>> states["Session"].enabled
        True
    """
    return {
        title: evaluate_tab(title, connected, session, unlocked) for title in titles
    }


class ServiceTabManager(QObject):
    """Keeps the diagnostic tabs in sync with the connection and ECU state.

    The manager owns no widgets of its own: it is given the
    :class:`~ui.widgets.tab_widget_enhanced.EnhancedTabWidget` of the panel and
    applies the rules of :func:`evaluate_tab` whenever the state changes.

    Args:
        tabs: The tab widget to drive, or ``None`` for a head-less manager.
        titles: The tab titles in display order.
        parent: Qt parent object.

    Attributes:
        connected: Whether the transport is connected.
        session: The active diagnostic session.
        unlocked: Whether security access has been granted.
    """

    #: Emitted with ``{title: TabState}`` after every state change.
    states_changed = Signal(dict)

    def __init__(
        self,
        tabs: Any = None,
        titles: Iterable[str] | None = None,
        parent: QObject | None = None,
    ) -> None:
        """Store the tab widget and initialise the state to disconnected."""
        super().__init__(parent)
        self.tabs = tabs
        self.titles: list[str] = list(titles or TAB_SERVICES)
        self.connected = False
        self.session = int(SessionType.DEFAULT)
        self.unlocked = False

    # -- state changes -------------------------------------------------------
    def set_connected(self, connected: bool) -> dict[str, TabState]:
        """Record the connection state and refresh the tabs."""
        self.connected = connected
        if not connected:
            self.session = int(SessionType.DEFAULT)
            self.unlocked = False
        return self.refresh()

    def set_session(self, session: int) -> dict[str, TabState]:
        """Record the active session and refresh the tabs."""
        self.session = session
        if session == int(SessionType.DEFAULT):
            self.unlocked = False
        return self.refresh()

    def set_unlocked(self, unlocked: bool) -> dict[str, TabState]:
        """Record the security state and refresh the tabs."""
        self.unlocked = unlocked
        return self.refresh()

    # -- evaluation ----------------------------------------------------------
    def states(self) -> dict[str, TabState]:
        """Return the current state of every managed tab."""
        return evaluate_tabs(self.titles, self.connected, self.session, self.unlocked)

    def refresh(self) -> dict[str, TabState]:
        """Apply the current states to the tab widget and publish them."""
        states = self.states()
        if self.tabs is not None:
            for index, title in enumerate(self.titles):
                state = states[title]
                self.tabs.set_tab_enabled(index, state.enabled, state.reason)
        self.states_changed.emit(states)
        return states

    def enabled_titles(self) -> list[str]:
        """Return the titles of the tabs the operator may currently use."""
        return [title for title, state in self.states().items() if state.enabled]

    def first_enabled(self) -> str | None:
        """Return the first usable tab title, or ``None`` when there is none."""
        enabled = self.enabled_titles()
        return enabled[0] if enabled else None
