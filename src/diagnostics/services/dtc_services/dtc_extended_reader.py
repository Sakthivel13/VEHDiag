"""DTC extended data reading - SID 0x19 sub-function 0x06."""
from __future__ import annotations

import logging

from ....core.enums.sid_enums import ServiceID
from ....core.models.dtc_model import DTC, DTCExtendedRecord, DTCStatus
from ....core.models.response_data_model import DiagnosticResponse
from ..base_service import BaseService
from .dtc_sub_functions import DTCSubFunction

_logger = logging.getLogger(__name__)

#: Record number requesting every stored extended data record.
ALL_RECORDS = 0xFF

#: Conventional meaning of the standard extended data record numbers.
STANDARD_RECORDS: dict[int, str] = {
    0x01: "occurrence counter",
    0x02: "aging counter",
    0x03: "aged counter",
    0x04: "healing counter",
    0x05: "operation cycle counter",
}


class DTCExtendedReader(BaseService):
    """Read the extended data records attached to a DTC."""

    service_id = int(ServiceID.READ_DTC_INFORMATION)
    min_request_length = 6
    has_sub_function = True

    def build_request(self, dtc: int, record_number: int = ALL_RECORDS) -> bytes:
        """Return ``19 06 <dtc> <record>``."""
        return (
            bytes([self.service_id, int(DTCSubFunction.REPORT_DTC_EXT_DATA_RECORD_BY_DTC_NUMBER)])
            + (dtc & 0xFFFFFF).to_bytes(3, "big")
            + bytes([record_number & 0xFF])
        )

    def parse_response(self, response: DiagnosticResponse) -> DTC:
        """Parse the extended data response into a :class:`DTC`."""
        raw = self.require_positive(response, min_length=6)
        code = int.from_bytes(raw[2:5], "big")
        result = DTC(code=code, status=DTCStatus(raw[5]))
        body = raw[6:]
        index = 0
        while index < len(body):
            record_number = body[index]
            data = bytes(body[index + 1 : index + 2])
            result.extended_records.append(
                DTCExtendedRecord(
                    record_number=record_number,
                    data=data,
                    parsed={"meaning": STANDARD_RECORDS.get(record_number, "manufacturer specific")},
                )
            )
            index += 2
        return result

    def read(self, dtc: int, record_number: int = ALL_RECORDS) -> DTC:
        """Read and parse the extended data records of *dtc*."""
        response = self.send(self.build_request(dtc, record_number), timeout=3.0)
        return self.parse_response(response)

    def read_occurrence_counter(self, dtc: int) -> int | None:
        """Return the occurrence counter (record 0x01) of *dtc*."""
        result = self.read(dtc, 0x01)
        for record in result.extended_records:
            if record.record_number == 0x01 and record.data:
                return record.data[0]
        return None


__all__ = ["DTCExtendedReader", "ALL_RECORDS", "STANDARD_RECORDS"]
