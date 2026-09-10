"""DTC snapshot (freeze frame) reading - SID 0x19 sub-function 0x04."""
from __future__ import annotations

import logging

from ....core.enums.sid_enums import ServiceID
from ....core.models.dtc_model import DTC, DTCSnapshotRecord, DTCStatus
from ....core.models.response_data_model import DiagnosticResponse
from ..base_service import BaseService
from .dtc_sub_functions import DTCSubFunction

_logger = logging.getLogger(__name__)

#: Record number requesting every stored snapshot.
ALL_RECORDS = 0xFF


class DTCSnapshotReader(BaseService):
    """Read the freeze frame data attached to a DTC."""

    service_id = int(ServiceID.READ_DTC_INFORMATION)
    min_request_length = 6
    has_sub_function = True

    def build_request(self, dtc: int, record_number: int = ALL_RECORDS) -> bytes:
        """Return ``19 04 <dtc> <record>``."""
        return (
            bytes([self.service_id, int(DTCSubFunction.REPORT_DTC_SNAPSHOT_RECORD_BY_DTC_NUMBER)])
            + (dtc & 0xFFFFFF).to_bytes(3, "big")
            + bytes([record_number & 0xFF])
        )

    def parse_response(self, response: DiagnosticResponse) -> DTC:
        """Parse the snapshot response into a :class:`DTC` with records."""
        raw = self.require_positive(response, min_length=6)
        code = int.from_bytes(raw[2:5], "big")
        result = DTC(code=code, status=DTCStatus(raw[5]))
        body = raw[6:]
        index = 0
        while index + 1 < len(body):
            record_number = body[index]
            did_count = body[index + 1]
            index += 2
            data = bytearray()
            for _ in range(did_count):
                if index + 2 > len(body):
                    break
                did = int.from_bytes(body[index : index + 2], "big")
                index += 2
                # Without a DID definition the remaining bytes are kept raw.
                data.extend(did.to_bytes(2, "big"))
                remaining = body[index:]
                data.extend(remaining)
                index = len(body)
            result.snapshots.append(
                DTCSnapshotRecord(record_number=record_number, data=bytes(data))
            )
        if not result.snapshots and body:
            result.snapshots.append(DTCSnapshotRecord(record_number=0x01, data=bytes(body)))
        return result

    def read(self, dtc: int, record_number: int = ALL_RECORDS) -> DTC:
        """Read and parse the snapshot records of *dtc*."""
        response = self.send(self.build_request(dtc, record_number), timeout=3.0)
        return self.parse_response(response)

    def list_identifications(self) -> list[tuple[int, int]]:
        """Return ``(dtc, record_number)`` pairs from sub-function 0x03."""
        payload = bytes([self.service_id, int(DTCSubFunction.REPORT_DTC_SNAPSHOT_IDENTIFICATION)])
        response = self.client.send_request(payload, timeout=3.0)
        raw = self.require_positive(response, min_length=2)
        body = raw[2:]
        pairs: list[tuple[int, int]] = []
        for index in range(0, len(body) - 3, 4):
            pairs.append((int.from_bytes(body[index : index + 3], "big"), body[index + 3]))
        return pairs


__all__ = ["DTCSnapshotReader", "ALL_RECORDS"]
