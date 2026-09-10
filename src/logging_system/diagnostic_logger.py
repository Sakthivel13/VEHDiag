"""Diagnostic activity logging (requests, responses, session changes)."""
from __future__ import annotations

import logging
from typing import Callable

from ..core.event_bus import Event, EventBus, EventType, get_event_bus
from ..core.models.log_entry_model import LogCategory, LogEntry, LogLevel
from ..core.models.response_data_model import DiagnosticResponse
from .communication_logger import decode_uds

_logger = logging.getLogger(__name__)

#: Events this logger listens to and the level it assigns to them.
EVENT_LEVELS: dict[EventType, LogLevel] = {
    EventType.DIAG_REQUEST_SENT: LogLevel.INFO,
    EventType.DIAG_RESPONSE_RECEIVED: LogLevel.INFO,
    EventType.DIAG_NRC_RECEIVED: LogLevel.WARNING,
    EventType.DIAG_SESSION_CHANGED: LogLevel.INFO,
    EventType.DIAG_SECURITY_UNLOCKED: LogLevel.INFO,
    EventType.DIAG_SECURITY_FAILED: LogLevel.WARNING,
    EventType.DIAG_DTC_READ: LogLevel.INFO,
    EventType.DIAG_DTC_CLEARED: LogLevel.INFO,
    EventType.DIAG_TRANSFER_STARTED: LogLevel.INFO,
    EventType.DIAG_TRANSFER_COMPLETE: LogLevel.INFO,
    EventType.DIAG_TRANSFER_FAILED: LogLevel.ERROR,
    EventType.DIAG_ECU_RESET: LogLevel.INFO,
}

#: Direction stamped on the entries of the events that carry a UDS payload.
#: Without this the entries look like plain text lines and every consumer that
#: filters on ``direction`` - the trace viewer, the live trace strip, the
#: communication export - silently drops them.
EVENT_DIRECTIONS: dict[EventType, str] = {
    EventType.DIAG_REQUEST_SENT: "TX",
    EventType.DIAG_RESPONSE_RECEIVED: "RX",
    EventType.DIAG_NRC_RECEIVED: "RX",
}


class DiagnosticLogger:
    """Records diagnostic level activity as human readable log entries.

    Args:
        sink: Callable receiving each produced :class:`LogEntry`.
        event_bus: Bus to subscribe to; ``None`` disables auto-subscription.
    """

    def __init__(
        self,
        sink: Callable[[LogEntry], None] | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        """Create the logger and optionally subscribe to the event bus."""
        self.sink = sink
        self.bus = event_bus
        self._tokens: list[int] = []
        if event_bus is not None:
            self.subscribe(event_bus)

    def subscribe(self, event_bus: EventBus | None = None) -> None:
        """Subscribe to every diagnostic event."""
        self.bus = event_bus or get_event_bus()
        for event_type in EVENT_LEVELS:
            self._tokens.append(self.bus.subscribe(event_type, self._on_event))

    def unsubscribe(self) -> None:
        """Remove the event bus subscriptions."""
        if self.bus is None:
            return
        for token in self._tokens:
            self.bus.unsubscribe(token)
        self._tokens.clear()

    def log_response(self, response: DiagnosticResponse) -> LogEntry:
        """Log a completed request/response exchange.

        The entry is stamped ``RX`` because ``raw`` holds the bytes that came
        back from the ECU; the matching request is logged separately as
        ``TX`` by :data:`EventType.DIAG_REQUEST_SENT`.
        """
        service, detail = decode_uds(response.request)
        level = LogLevel.WARNING if response.is_negative else LogLevel.INFO
        if response.timed_out:
            level = LogLevel.ERROR
        entry = LogEntry(
            message=f"{service} {detail}: {response.summary()}".strip(),
            level=level,
            category=LogCategory.DIAG,
            timestamp=response.timestamp,
            direction="RX",
            data=response.raw,
            decoded_service=service,
            decoded_detail=detail,
        )
        self._emit(entry)
        return entry

    def _on_event(self, event: Event) -> None:
        """Convert a diagnostic event into a log entry."""
        level = EVENT_LEVELS.get(event.type, LogLevel.INFO)
        message = self._describe(event)
        entry = LogEntry(
            message=message,
            level=level,
            category=LogCategory.DIAG,
            timestamp=event.timestamp,
        )
        payload = event.get("payload") or event.get("response") or event.get("request")
        if isinstance(payload, (bytes, bytearray)):
            entry.data = bytes(payload)
            entry.direction = EVENT_DIRECTIONS.get(event.type, "")
            entry.decoded_service, entry.decoded_detail = decode_uds(entry.data)
        self._emit(entry)

    @staticmethod
    def _describe(event: Event) -> str:
        """Return a readable sentence describing *event*."""
        data = event.data
        if event.type is EventType.DIAG_SESSION_CHANGED:
            return f"diagnostic session changed to {data.get('label', data.get('session'))}"
        if event.type is EventType.DIAG_SECURITY_UNLOCKED:
            return f"security level 0x{int(data.get('level', 0)):02X} unlocked"
        if event.type is EventType.DIAG_SECURITY_FAILED:
            return f"security unlock failed (NRC 0x{int(data.get('nrc', 0)):02X})"
        if event.type is EventType.DIAG_NRC_RECEIVED:
            return f"negative response: {data.get('info', '')}"
        if event.type is EventType.DIAG_DTC_READ:
            return f"read {data.get('count', 0)} DTC(s)"
        if event.type is EventType.DIAG_DTC_CLEARED:
            return f"cleared DTC group 0x{int(data.get('group', 0xFFFFFF)):06X}"
        if event.type is EventType.DIAG_TRANSFER_STARTED:
            return f"transfer started: {data.get('size', 0)} bytes to 0x{int(data.get('address', 0)):08X}"
        if event.type in (EventType.DIAG_TRANSFER_COMPLETE, EventType.DIAG_TRANSFER_FAILED):
            return str(data.get("summary", event.type.value))
        if event.type is EventType.DIAG_ECU_RESET:
            return f"ECU reset requested ({data.get('name', '')})"
        if event.type is EventType.DIAG_REQUEST_SENT:
            payload = data.get("payload", b"")
            service, detail = decode_uds(bytes(payload)) if payload else ("", "")
            return f"request sent: {service} {detail}".strip()
        if event.type is EventType.DIAG_RESPONSE_RECEIVED:
            elapsed = data.get("elapsed_ms", 0.0)
            return f"response received in {float(elapsed):.1f} ms"
        return event.type.value

    def _emit(self, entry: LogEntry) -> None:
        """Hand *entry* to the sink, ignoring sink failures."""
        if self.sink is None:
            return
        try:
            self.sink(entry)
        except Exception:  # noqa: BLE001
            _logger.exception("diagnostic log sink failed")


__all__ = ["DiagnosticLogger", "EVENT_DIRECTIONS", "EVENT_LEVELS"]
