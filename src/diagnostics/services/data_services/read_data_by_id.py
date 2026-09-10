"""ReadDataByIdentifier - SID 0x22."""
from __future__ import annotations

import logging
import time

from ....core.enums.data_format_enums import ByteOrder, DataFormat
from ....core.enums.sid_enums import ServiceID
from ....core.exceptions import RequestValidationError
from ....core.models.did_model import DIDDefinition, DIDRegistry, DIDValue
from ....core.models.response_data_model import DiagnosticResponse
from ..base_service import BaseService

_logger = logging.getLogger(__name__)


def build_registry(definitions: dict[int, dict[str, object]] | None) -> DIDRegistry:
    """Build a :class:`DIDRegistry` from the YAML definition table."""
    registry = DIDRegistry()
    for did, entry in (definitions or {}).items():
        registry.add(
            DIDDefinition(
                did=did,
                name=str(entry.get("name", "")),
                description=str(entry.get("description", "")),
                length=int(entry["length"]) if entry.get("length") is not None else None,
                data_format=DataFormat(str(entry.get("format", "HEX"))),
                byte_order=ByteOrder.BIG_ENDIAN,
                factor=float(entry.get("factor", 1.0)),
                offset=float(entry.get("offset", 0.0)),
                unit=str(entry.get("unit", "")),
                writable=bool(entry.get("writable", False)),
            )
        )
    return registry


class ReadDataByIdentifier(BaseService):
    """Read one or more data records identified by a DID.

    Args:
        client: UDS client used for transmission.
        registry: Known DID definitions used to parse and label the values.
    """

    service_id = int(ServiceID.READ_DATA_BY_IDENTIFIER)
    min_request_length = 3
    has_sub_function = False

    def __init__(self, client, registry: DIDRegistry | None = None) -> None:  # noqa: ANN001
        """Store the client and the DID registry."""
        super().__init__(client)
        self.registry = registry or DIDRegistry()

    def build_request(self, *dids: int) -> bytes:
        """Return ``22 <did hi> <did lo> ...``.

        Raises:
            RequestValidationError: No DID was supplied or one is out of range.
        """
        if not dids:
            raise RequestValidationError("at least one data identifier is required")
        payload = bytearray([self.service_id])
        for did in dids:
            if not 0 <= did <= 0xFFFF:
                raise RequestValidationError(
                    "a data identifier must fit into two bytes", {"value": hex(did)}
                )
            payload.extend(did.to_bytes(2, "big"))
        return bytes(payload)

    def parse_response(self, response: DiagnosticResponse) -> list[DIDValue]:
        """Split the response into one :class:`DIDValue` per identifier.

        When a definition with a fixed length is known the record boundaries
        are taken from it; otherwise the remaining bytes belong to the last
        identifier.
        """
        raw = self.require_positive(response, min_length=3)
        body = raw[1:]
        values: list[DIDValue] = []
        index = 0
        while index + 2 <= len(body):
            did = int.from_bytes(body[index : index + 2], "big")
            index += 2
            definition = self.registry.get(did)
            if definition is not None and definition.length:
                data = body[index : index + definition.length]
                index += definition.length
            else:
                data = body[index:]
                index = len(body)
            value = DIDValue(
                did=did, raw=bytes(data), definition=definition, timestamp=time.time()
            )
            value.parsed = self._interpret(value)
            values.append(value)
        return values

    def _interpret(self, value: DIDValue) -> object:
        """Convert the raw bytes according to the DID definition."""
        definition = value.definition
        if definition is None:
            return value.hex_value
        fmt = definition.data_format
        if fmt is DataFormat.ASCII:
            return value.raw.decode("ascii", errors="replace").strip("\x00").strip()
        if fmt in (DataFormat.DEC_UNSIGNED, DataFormat.MOT):
            return int.from_bytes(value.raw, "big") if value.raw else 0
        if fmt is DataFormat.DEC_SIGNED:
            return int.from_bytes(value.raw, "big", signed=True) if value.raw else 0
        if fmt is DataFormat.BCD:
            return "".join(f"{b >> 4}{b & 0x0F}" for b in value.raw)
        if fmt is DataFormat.PHYSICAL:
            raw_int = int.from_bytes(value.raw, "big") if value.raw else 0
            physical = raw_int * definition.factor + definition.offset
            return f"{physical:.3f} {definition.unit}".strip()
        return value.hex_value

    def execute(self, *dids: int) -> list[DIDValue]:
        """Read *dids* and return the parsed values."""
        response = self.send(self.build_request(*dids))
        return self.parse_response(response)

    def read_one(self, did: int) -> DIDValue | None:
        """Read a single DID, returning ``None`` when the ECU rejects it."""
        try:
            values = self.execute(did)
        except Exception:  # noqa: BLE001 - the caller only needs the value
            return None
        return values[0] if values else None

    def read_many(self, dids: list[int], batch_size: int = 4) -> list[DIDValue]:
        """Read many DIDs, splitting them into batches of *batch_size*."""
        results: list[DIDValue] = []
        for index in range(0, len(dids), max(1, batch_size)):
            chunk = dids[index : index + batch_size]
            try:
                results.extend(self.execute(*chunk))
            except Exception:  # noqa: BLE001 - fall back to individual reads
                for did in chunk:
                    value = self.read_one(did)
                    if value is not None:
                        results.append(value)
        return results

    def read_identification(self) -> dict[str, object]:
        """Read the standard identification DIDs (0xF187..0xF195)."""
        standard = [0xF190, 0xF187, 0xF188, 0xF189, 0xF18A, 0xF18C, 0xF191, 0xF195]
        return {value.name or f"{value.did:04X}": value.parsed for value in self.read_many(standard, 1)}


__all__ = ["ReadDataByIdentifier", "build_registry"]
