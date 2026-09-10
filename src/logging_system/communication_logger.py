"""Raw communication (TX/RX) logging with UDS decoding."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from ..core.enums.nrc_enums import describe_nrc
from ..core.enums.protocol_enums import MessageDirection
from ..core.enums.sid_enums import (
    NEGATIVE_RESPONSE_SID,
    POSITIVE_RESPONSE_OFFSET,
    ServiceID,
)
from ..core.event_bus import Event, EventBus, EventType, get_event_bus
from ..core.models.log_entry_model import LogCategory, LogEntry, LogLevel
from ..core.models.message_model import BusMessage

_logger = logging.getLogger(__name__)


def decode_uds(payload: bytes) -> tuple[str, str]:
    """Return ``(service name, detail)`` for a UDS payload.

    Example:
        >>> decode_uds(bytes.fromhex("22F190"))
        ('ReadDataByIdentifier', 'DID 0xF190')
        >>> decode_uds(bytes.fromhex("7F2231"))[0]
        'NegativeResponse'
    """
    if not payload:
        return "", ""
    first = payload[0]
    if first == NEGATIVE_RESPONSE_SID and len(payload) >= 3:
        service = ServiceID.from_byte(payload[1])
        name = service.pretty_name if service else f"0x{payload[1]:02X}"
        return "NegativeResponse", f"{name}: {describe_nrc(payload[2])}"
    request_sid = first
    is_response = False
    service = ServiceID.from_byte(first)
    if service is None:
        candidate = (first - POSITIVE_RESPONSE_OFFSET) & 0xFF
        service = ServiceID.from_byte(candidate)
        if service is not None:
            request_sid, is_response = candidate, True
    if service is None:
        return f"Unknown(0x{first:02X})", ""
    name = service.pretty_name + (" response" if is_response else "")
    detail = ""
    if request_sid in (int(ServiceID.READ_DATA_BY_IDENTIFIER), int(ServiceID.WRITE_DATA_BY_IDENTIFIER)):
        if len(payload) >= 3:
            detail = f"DID 0x{int.from_bytes(payload[1:3], 'big'):04X}"
    elif request_sid == int(ServiceID.DIAGNOSTIC_SESSION_CONTROL) and len(payload) >= 2:
        detail = f"session 0x{payload[1] & 0x7F:02X}"
    elif request_sid == int(ServiceID.READ_DTC_INFORMATION) and len(payload) >= 2:
        detail = f"sub-function 0x{payload[1]:02X}"
    elif request_sid == int(ServiceID.SECURITY_ACCESS) and len(payload) >= 2:
        detail = f"level 0x{payload[1]:02X}"
    elif request_sid == int(ServiceID.ROUTINE_CONTROL) and len(payload) >= 4:
        detail = f"routine 0x{int.from_bytes(payload[2:4], 'big'):04X}"
    return name, detail


@dataclass(slots=True)
class CommunicationStatistics:
    """Counters describing the logged traffic."""

    tx_frames: int = 0
    rx_frames: int = 0
    tx_bytes: int = 0
    rx_bytes: int = 0
    negative_responses: int = 0


class CommunicationLogger:
    """Turns bus messages into log entries and subscribes to the event bus.

    Args:
        sink: Callable receiving each produced :class:`LogEntry`.
        event_bus: Bus to subscribe to; ``None`` disables auto-subscription.
        decode: Annotate the entries with the decoded UDS service.
    """

    def __init__(
        self,
        sink: "Callable[[LogEntry], None] | None" = None,  # noqa: F821 - forward ref
        event_bus: EventBus | None = None,
        decode: bool = True,
    ) -> None:
        """Create the logger and optionally subscribe to the event bus."""
        self.sink = sink
        self.decode = decode
        self.statistics = CommunicationStatistics()
        self.bus = event_bus
        self._tokens: list[int] = []
        if event_bus is not None:
            self.subscribe(event_bus)

    def subscribe(self, event_bus: EventBus | None = None) -> None:
        """Subscribe to the TX and RX events of *event_bus*."""
        self.bus = event_bus or get_event_bus()
        self._tokens.append(self.bus.subscribe(EventType.COMM_MESSAGE_TX, self._on_event))
        self._tokens.append(self.bus.subscribe(EventType.COMM_MESSAGE_RX, self._on_event))

    def unsubscribe(self) -> None:
        """Remove the event bus subscriptions."""
        if self.bus is None:
            return
        for token in self._tokens:
            self.bus.unsubscribe(token)
        self._tokens.clear()

    def log_message(self, message: BusMessage) -> LogEntry:
        """Convert *message* into a :class:`LogEntry` and emit it."""
        entry = LogEntry(
            level=LogLevel.DEBUG,
            category=LogCategory.COMM,
            timestamp=message.timestamp,
            direction=message.direction.value,
            protocol=message.protocol.value,
            channel=message.channel,
            can_id=message.id_text,
            data=message.data,
        )
        if self.decode:
            entry.decoded_service, entry.decoded_detail = decode_uds(message.data)
            if entry.decoded_service == "NegativeResponse":
                entry.level = LogLevel.WARNING
                self.statistics.negative_responses += 1
        if message.direction is MessageDirection.TX:
            self.statistics.tx_frames += 1
            self.statistics.tx_bytes += len(message.data)
        else:
            self.statistics.rx_frames += 1
            self.statistics.rx_bytes += len(message.data)
        self._emit(entry)
        return entry

    def log_payload(self, payload: bytes, direction: str = "TX", protocol: str = "UDS") -> LogEntry:
        """Log an assembled diagnostic payload (above the transport layer)."""
        entry = LogEntry(
            level=LogLevel.INFO,
            category=LogCategory.DIAG,
            direction=direction,
            protocol=protocol,
            data=payload,
        )
        if self.decode:
            entry.decoded_service, entry.decoded_detail = decode_uds(payload)
        self._emit(entry)
        return entry

    def _on_event(self, event: Event) -> None:
        """Handle a TX/RX event published on the bus."""
        message = event.get("message")
        if isinstance(message, BusMessage):
            self.log_message(message)
            return
        payload = event.get("payload")
        if isinstance(payload, (bytes, bytearray)):
            direction = "TX" if event.type is EventType.COMM_MESSAGE_TX else "RX"
            self.log_payload(bytes(payload), direction, str(event.get("protocol", "UDS")))

    def _emit(self, entry: LogEntry) -> None:
        """Hand *entry* to the sink, ignoring sink failures."""
        if self.sink is None:
            return
        try:
            self.sink(entry)
        except Exception:  # noqa: BLE001 - logging must never break the bus
            _logger.exception("communication log sink failed")


__all__ = ["CommunicationLogger", "CommunicationStatistics", "decode_uds"]
