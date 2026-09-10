"""ResponseOnEvent - SID 0x86."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import IntEnum

from ....core.enums.sid_enums import ServiceID
from ....core.exceptions import RequestValidationError
from ....core.models.response_data_model import DiagnosticResponse
from ..base_service import BaseService

_logger = logging.getLogger(__name__)


class EventType(IntEnum):
    """eventType sub-functions of ResponseOnEvent."""

    STOP_RESPONSE_ON_EVENT = 0x00
    ON_DTC_STATUS_CHANGE = 0x01
    ON_TIMER_INTERRUPT = 0x02
    ON_CHANGE_OF_DATA_IDENTIFIER = 0x03
    REPORT_ACTIVATED_EVENTS = 0x04
    START_RESPONSE_ON_EVENT = 0x05
    CLEAR_RESPONSE_ON_EVENT = 0x06
    ON_COMPARISON_OF_VALUES = 0x07


#: Timer rates used by :attr:`EventType.ON_TIMER_INTERRUPT`.
TIMER_RATES: dict[int, str] = {0x01: "slow", 0x02: "medium", 0x03: "fast"}


@dataclass(slots=True)
class EventConfiguration:
    """One configured event and the service it triggers."""

    event_type: int
    window_time: int = 0x02
    event_parameters: bytes = b""
    service_to_respond_to: bytes = b""

    def to_bytes(self, store: bool = False) -> bytes:
        """Return the request body after the service identifier."""
        sub = (self.event_type & 0x3F) | (0x40 if store else 0x00)
        return (
            bytes([sub, self.window_time & 0xFF])
            + self.event_parameters
            + self.service_to_respond_to
        )


class ResponseOnEvent(BaseService):
    """Configure the ECU to answer autonomously when an event occurs."""

    service_id = int(ServiceID.RESPONSE_ON_EVENT)
    min_request_length = 3
    has_sub_function = True

    def build_request(self, configuration: EventConfiguration, store: bool = False) -> bytes:
        """Return ``86 <event type> <window> [parameters] [service]``.

        Raises:
            RequestValidationError: The event type is outside 0x00..0x07.
        """
        if not 0x00 <= configuration.event_type <= 0x07:
            raise RequestValidationError("the event type must be in 0x00..0x07")
        return bytes([self.service_id]) + configuration.to_bytes(store)

    def parse_response(self, response: DiagnosticResponse) -> bool:
        """Return ``True`` when the configuration was accepted."""
        return response.is_positive()

    def on_dtc_status_change(self, status_mask: int, service_payload: bytes, window: int = 0x02) -> bool:
        """Trigger *service_payload* whenever a DTC status bit changes."""
        configuration = EventConfiguration(
            event_type=int(EventType.ON_DTC_STATUS_CHANGE),
            window_time=window,
            event_parameters=bytes([status_mask & 0xFF]),
            service_to_respond_to=service_payload,
        )
        return self.parse_response(self.send(self.build_request(configuration)))

    def on_did_change(self, did: int, service_payload: bytes, window: int = 0x02) -> bool:
        """Trigger *service_payload* when the value of *did* changes."""
        configuration = EventConfiguration(
            event_type=int(EventType.ON_CHANGE_OF_DATA_IDENTIFIER),
            window_time=window,
            event_parameters=(did & 0xFFFF).to_bytes(2, "big"),
            service_to_respond_to=service_payload,
        )
        return self.parse_response(self.send(self.build_request(configuration)))

    def start(self) -> bool:
        """Activate the previously configured events."""
        configuration = EventConfiguration(int(EventType.START_RESPONSE_ON_EVENT))
        return self.parse_response(self.send(self.build_request(configuration)))

    def stop(self) -> bool:
        """Stop the event driven responses."""
        configuration = EventConfiguration(int(EventType.STOP_RESPONSE_ON_EVENT))
        return self.parse_response(self.send(self.build_request(configuration)))

    def clear(self) -> bool:
        """Delete every configured event."""
        configuration = EventConfiguration(int(EventType.CLEAR_RESPONSE_ON_EVENT))
        return self.parse_response(self.send(self.build_request(configuration)))

    def execute(self, configuration: EventConfiguration, store: bool = False) -> bool:
        """Send one ResponseOnEvent configuration."""
        return self.parse_response(self.send(self.build_request(configuration, store)))


__all__ = ["ResponseOnEvent", "EventType", "EventConfiguration", "TIMER_RATES"]
