"""DynamicallyDefineDataIdentifier - SID 0x2C."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import IntEnum

from ....core.enums.sid_enums import ServiceID
from ....core.exceptions import RequestValidationError
from ....core.models.response_data_model import DiagnosticResponse
from ..base_service import BaseService

_logger = logging.getLogger(__name__)


class DefinitionMode(IntEnum):
    """Sub-functions of SID 0x2C."""

    DEFINE_BY_IDENTIFIER = 0x01
    DEFINE_BY_MEMORY_ADDRESS = 0x02
    CLEAR_DYNAMICALLY_DEFINED = 0x03


@dataclass(slots=True)
class SourceDefinition:
    """One source record contributing to a dynamic identifier.

    Attributes:
        source_did: DID the bytes are taken from.
        position: 1-based position of the first byte inside the source record.
        size: Number of bytes taken from the source record.
    """

    source_did: int
    position: int = 1
    size: int = 1

    def to_bytes(self) -> bytes:
        """Return the four byte source record."""
        return (self.source_did & 0xFFFF).to_bytes(2, "big") + bytes(
            [self.position & 0xFF, self.size & 0xFF]
        )


class DynamicallyDefineDataIdentifier(BaseService):
    """Compose new data identifiers from existing records or memory ranges."""

    service_id = int(ServiceID.DYNAMICALLY_DEFINE_DATA_IDENTIFIER)
    min_request_length = 4
    has_sub_function = True

    def build_request(
        self,
        mode: int,
        dynamic_did: int,
        sources: list[SourceDefinition] | None = None,
    ) -> bytes:
        """Return the request for *mode*.

        Raises:
            RequestValidationError: A define request has no source records.
        """
        payload = bytearray([self.service_id, mode & 0xFF])
        payload.extend((dynamic_did & 0xFFFF).to_bytes(2, "big"))
        if mode == int(DefinitionMode.DEFINE_BY_IDENTIFIER):
            if not sources:
                raise RequestValidationError("defining a dynamic DID requires source records")
            for source in sources:
                payload.extend(source.to_bytes())
        return bytes(payload)

    def parse_response(self, response: DiagnosticResponse) -> bool:
        """Return ``True`` when the definition was accepted."""
        return response.is_positive()

    def define_by_identifier(self, dynamic_did: int, sources: list[SourceDefinition]) -> bool:
        """Define *dynamic_did* from existing data identifiers."""
        payload = self.build_request(int(DefinitionMode.DEFINE_BY_IDENTIFIER), dynamic_did, sources)
        return self.parse_response(self.send(payload))

    def define_by_memory(
        self,
        dynamic_did: int,
        address: int,
        size: int,
        address_bytes: int = 4,
        length_bytes: int = 2,
    ) -> bool:
        """Define *dynamic_did* from a memory range."""
        alfid = ((length_bytes & 0x0F) << 4) | (address_bytes & 0x0F)
        payload = (
            bytes([self.service_id, int(DefinitionMode.DEFINE_BY_MEMORY_ADDRESS)])
            + (dynamic_did & 0xFFFF).to_bytes(2, "big")
            + bytes([alfid])
            + address.to_bytes(address_bytes, "big")
            + size.to_bytes(length_bytes, "big")
        )
        return self.parse_response(self.send(payload))

    def clear(self, dynamic_did: int) -> bool:
        """Delete a previously defined dynamic identifier."""
        payload = self.build_request(int(DefinitionMode.CLEAR_DYNAMICALLY_DEFINED), dynamic_did)
        return self.parse_response(self.send(payload))

    def execute(self, dynamic_did: int, sources: list[SourceDefinition]) -> bool:
        """Alias of :meth:`define_by_identifier`."""
        return self.define_by_identifier(dynamic_did, sources)


__all__ = ["DynamicallyDefineDataIdentifier", "DefinitionMode", "SourceDefinition"]
