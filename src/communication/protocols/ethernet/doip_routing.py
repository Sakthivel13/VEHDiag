"""DoIP routing activation handling."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from ....core.exceptions import ProtocolError
from .doip_connection import DoIPConnection
from .doip_message import (
    DoIPMessage,
    PayloadType,
    RoutingActivationResponseCode,
    build_routing_activation,
)

_logger = logging.getLogger(__name__)

#: Activation types defined by ISO 13400-2.
ACTIVATION_TYPES: dict[int, str] = {
    0x00: "default",
    0x01: "WWH-OBD",
    0xE0: "central security",
}


@dataclass(slots=True)
class RoutingActivationResult:
    """Outcome of a routing activation exchange."""

    code: int
    source_address: int = 0
    entity_address: int = 0
    oem_specific: bytes = b""

    @property
    def response(self) -> RoutingActivationResponseCode | None:
        """Return the decoded response code, if standardised."""
        try:
            return RoutingActivationResponseCode(self.code)
        except ValueError:
            return None

    @property
    def success(self) -> bool:
        """Return ``True`` when routing was activated."""
        decoded = self.response
        return bool(decoded and decoded.is_success)

    @property
    def description(self) -> str:
        """Return a readable description of the response code."""
        decoded = self.response
        if decoded is None:
            return f"unknown routing activation code 0x{self.code:02X}"
        return decoded.name.replace("_", " ").lower()


def activate_routing(
    connection: DoIPConnection,
    source_address: int,
    activation_type: int = 0x00,
    timeout: float = 2.0,
) -> RoutingActivationResult:
    """Perform a routing activation on an open DoIP connection.

    Args:
        connection: An open :class:`DoIPConnection`.
        source_address: Logical address of the tester.
        activation_type: Activation type, see :data:`ACTIVATION_TYPES`.
        timeout: Response timeout in seconds.

    Returns:
        The parsed result of the activation.

    Raises:
        ProtocolError: The entity answered with an unexpected payload type.
    """
    request = build_routing_activation(source_address, activation_type)
    response = connection.request(request, timeout)
    if response.payload_type != PayloadType.ROUTING_ACTIVATION_RESPONSE:
        raise ProtocolError(
            "unexpected answer to the routing activation request",
            {"received": response.type_name},
        )
    payload = response.payload
    if len(payload) < 5:
        raise ProtocolError("truncated routing activation response")
    result = RoutingActivationResult(
        code=payload[4],
        source_address=int.from_bytes(payload[0:2], "big"),
        entity_address=int.from_bytes(payload[2:4], "big"),
        oem_specific=bytes(payload[9:]) if len(payload) > 9 else b"",
    )
    _logger.info("routing activation: %s", result.description)
    return result


def alive_check(connection: DoIPConnection, timeout: float = 2.0) -> bool:
    """Send an alive check and return ``True`` when the entity answers."""
    try:
        response = connection.request(DoIPMessage(PayloadType.ALIVE_CHECK_REQUEST), timeout)
    except Exception:  # noqa: BLE001 - the caller only needs the boolean
        return False
    return response.payload_type == PayloadType.ALIVE_CHECK_RESPONSE


__all__ = [
    "ACTIVATION_TYPES",
    "RoutingActivationResult",
    "activate_routing",
    "alive_check",
]
