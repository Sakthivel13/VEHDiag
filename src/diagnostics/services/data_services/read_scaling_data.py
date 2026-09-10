"""ReadScalingDataByIdentifier - SID 0x24."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ....core.enums.sid_enums import ServiceID
from ....core.models.response_data_model import DiagnosticResponse
from ..base_service import BaseService

_logger = logging.getLogger(__name__)

#: Scaling byte high nibble meanings defined by ISO 14229-1.
SCALING_TYPES: dict[int, str] = {
    0x0: "unsigned numeric",
    0x1: "signed numeric",
    0x2: "bit mapped reported without mask",
    0x3: "bit mapped reported with mask",
    0x4: "binary coded decimal",
    0x5: "state encoded variable",
    0x6: "ASCII",
    0x7: "signed floating point",
    0x8: "packet",
    0x9: "formula",
    0xA: "unit / format",
    0xB: "state and connection type",
}


@dataclass(slots=True)
class ScalingEntry:
    """One scaling byte plus its extension bytes."""

    scaling_type: int
    size: int
    extension: bytes = b""

    @property
    def type_name(self) -> str:
        """Return the readable scaling type."""
        return SCALING_TYPES.get(self.scaling_type, f"reserved (0x{self.scaling_type:X})")

    def __str__(self) -> str:  # noqa: D105 - trivial
        return f"{self.type_name} x{self.size}"


@dataclass(slots=True)
class ScalingInfo:
    """The complete scaling description of one data identifier."""

    did: int
    entries: list[ScalingEntry] = field(default_factory=list)
    raw: bytes = b""

    @property
    def total_size(self) -> int:
        """Return the total data size described by the entries."""
        return sum(entry.size for entry in self.entries)


class ReadScalingDataByIdentifier(BaseService):
    """Read the scaling information attached to a data identifier."""

    service_id = int(ServiceID.READ_SCALING_DATA_BY_IDENTIFIER)
    min_request_length = 3
    has_sub_function = False

    def build_request(self, did: int) -> bytes:
        """Return ``24 <did hi> <did lo>``."""
        return bytes([self.service_id]) + (did & 0xFFFF).to_bytes(2, "big")

    def parse_response(self, response: DiagnosticResponse) -> ScalingInfo:
        """Parse the scaling bytes of a 0x64 response."""
        raw = self.require_positive(response, min_length=4)
        did = int.from_bytes(raw[1:3], "big")
        info = ScalingInfo(did=did, raw=raw)
        body = raw[3:]
        index = 0
        while index < len(body):
            scaling_byte = body[index]
            index += 1
            scaling_type = (scaling_byte >> 4) & 0x0F
            size = scaling_byte & 0x0F
            extension = b""
            if scaling_type in (0x9, 0xA):  # formula and unit carry extra bytes
                extension = bytes(body[index : index + size])
                index += size
            info.entries.append(ScalingEntry(scaling_type, size, extension))
        return info

    def execute(self, did: int) -> ScalingInfo:
        """Read the scaling information of *did*."""
        return self.parse_response(self.send(self.build_request(did)))


__all__ = ["ReadScalingDataByIdentifier", "ScalingInfo", "ScalingEntry", "SCALING_TYPES"]
