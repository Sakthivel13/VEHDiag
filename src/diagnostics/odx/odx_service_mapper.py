"""Map ODX diagnostic services onto the platform services."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from ...core.enums.sid_enums import ServiceID
from ...core.models.did_model import DIDDefinition, DIDRegistry
from ...core.enums.data_format_enums import DataFormat
from .odx_database import ODXDatabase
from .odx_parser import DiagService

_logger = logging.getLogger(__name__)

#: ODX semantics mapped onto UDS service identifiers.
SEMANTIC_TO_SID: dict[str, int] = {
    "SESSION": int(ServiceID.DIAGNOSTIC_SESSION_CONTROL),
    "ECU-RESET": int(ServiceID.ECU_RESET),
    "CLEARDIAGNOSTICINFORMATION": int(ServiceID.CLEAR_DIAGNOSTIC_INFORMATION),
    "FAULTREAD": int(ServiceID.READ_DTC_INFORMATION),
    "FAULTCLEAR": int(ServiceID.CLEAR_DIAGNOSTIC_INFORMATION),
    "IDENTIFICATION": int(ServiceID.READ_DATA_BY_IDENTIFIER),
    "DATA": int(ServiceID.READ_DATA_BY_IDENTIFIER),
    "READ": int(ServiceID.READ_DATA_BY_IDENTIFIER),
    "WRITE": int(ServiceID.WRITE_DATA_BY_IDENTIFIER),
    "SECURITY": int(ServiceID.SECURITY_ACCESS),
    "ROUTINE": int(ServiceID.ROUTINE_CONTROL),
    "IO": int(ServiceID.INPUT_OUTPUT_CONTROL_BY_IDENTIFIER),
    "TESTERPRESENT": int(ServiceID.TESTER_PRESENT),
}

#: ODX base data types mapped onto the platform data formats.
BASE_TYPE_TO_FORMAT: dict[str, DataFormat] = {
    "A_UINT32": DataFormat.DEC_UNSIGNED,
    "A_INT32": DataFormat.DEC_SIGNED,
    "A_FLOAT32": DataFormat.FLOAT32,
    "A_FLOAT64": DataFormat.FLOAT64,
    "A_ASCIISTRING": DataFormat.ASCII,
    "A_UTF8STRING": DataFormat.ASCII,
    "A_BYTEFIELD": DataFormat.HEX,
}


@dataclass(slots=True)
class MappedService:
    """An ODX service linked to a platform service identifier."""

    odx: DiagService
    service_id: int
    payload: bytes

    @property
    def name(self) -> str:
        """Return the readable service name."""
        return self.odx.label

    @property
    def supported(self) -> bool:
        """Return ``True`` when the platform implements the service."""
        return ServiceID.from_byte(self.service_id) is not None

    def __str__(self) -> str:  # noqa: D105 - trivial
        state = "supported" if self.supported else "unsupported"
        return f"{self.name} -> 0x{self.service_id:02X} ({state})"


class ODXServiceMapper:
    """Turns ODX content into something the platform can execute.

    Args:
        database: The loaded ODX database.

    Example:
        >>> mapper = ODXServiceMapper(ODXDatabase())
        >>> mapper.map_all()
        []
    """

    def __init__(self, database: ODXDatabase) -> None:
        """Store the database."""
        self.database = database

    def map_service(self, service: DiagService) -> MappedService:
        """Map one ODX service onto a UDS service identifier."""
        service_id = service.service_id
        if not service_id:
            service_id = SEMANTIC_TO_SID.get(service.semantic.upper(), 0)
        payload = service.request_bytes or (bytes([service_id]) if service_id else b"")
        return MappedService(odx=service, service_id=service_id, payload=payload)

    def map_all(self, variant: str | None = None) -> list[MappedService]:
        """Map every service of one variant, or of the whole database."""
        return [self.map_service(service) for service in self.database.services(variant)]

    def supported_services(self, variant: str | None = None) -> list[MappedService]:
        """Return only the services the platform can execute."""
        return [mapped for mapped in self.map_all(variant) if mapped.supported]

    def build_did_registry(self, variant: str | None = None) -> DIDRegistry:
        """Derive a :class:`DIDRegistry` from the ODX data object properties."""
        registry = DIDRegistry()
        entries = (
            [self.database.variants[variant]]
            if variant and variant in self.database.variants
            else list(self.database.variants.values())
        )
        for entry in entries:
            for name, dop in entry.dops.items():
                identifier = self._identifier_from_name(name)
                if identifier is None:
                    continue
                registry.add(
                    DIDDefinition(
                        did=identifier,
                        name=dop.long_name or dop.short_name,
                        length=dop.byte_length,
                        data_format=BASE_TYPE_TO_FORMAT.get(dop.base_type, DataFormat.HEX),
                        factor=dop.compute.factor,
                        offset=dop.compute.offset,
                        unit=dop.compute.unit,
                    )
                )
        return registry

    def build_sequence(self, variant: str | None = None) -> dict[str, Any]:
        """Return a developer mode sequence covering every mapped service."""
        steps = []
        for order, mapped in enumerate(self.supported_services(variant), start=1):
            steps.append(
                {
                    "service": f"0x{mapped.service_id:02X}",
                    "name": mapped.name,
                    "enabled": True,
                    "test_file": "",
                    "payload": mapped.payload.hex(" ").upper(),
                    "mode": "PAYLOAD",
                    "order": order,
                }
            )
        return {"name": f"ODX {variant or 'all variants'}", "test_sequence": steps}

    @staticmethod
    def _identifier_from_name(name: str) -> int | None:
        """Extract a hexadecimal identifier embedded in a DOP name."""
        import re

        match = re.search(r"(?:^|[_\-])([0-9A-Fa-f]{4})(?:$|[_\-])", name)
        if match is None:
            return None
        try:
            return int(match.group(1), 16)
        except ValueError:
            return None


__all__ = ["ODXServiceMapper", "MappedService", "SEMANTIC_TO_SID", "BASE_TYPE_TO_FORMAT"]
