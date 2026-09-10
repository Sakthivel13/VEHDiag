"""ReadDTCInformation - SID 0x19."""
from __future__ import annotations

import logging

from ....core.enums.sid_enums import ServiceID
from ....core.event_bus import EventType
from ....core.exceptions import InvalidResponseError, RequestValidationError
from ....core.models.dtc_model import DTC, DTCReport, DTCStatus
from ....core.models.response_data_model import DiagnosticResponse
from ..base_service import BaseService
from .dtc_parser import build_name_lookup, parse_dtc_list
from .dtc_status_mask import MASK_ALL, StatusMask
from .dtc_sub_functions import DTCSubFunction, SubFunctionSpec, describe_sub_function

_logger = logging.getLogger(__name__)


class ReadDTCInformation(BaseService):
    """Read diagnostic trouble codes and their attached records.

    Args:
        client: UDS client used for transmission.
        catalogue: Optional mapping of hex DTC strings to descriptions, taken
            from ``config/dtc_definitions.yaml``.
    """

    service_id = int(ServiceID.READ_DTC_INFORMATION)
    min_request_length = 2
    has_sub_function = True

    def __init__(self, client, catalogue: dict[str, str] | None = None) -> None:  # noqa: ANN001
        """Store the client and build the DTC name lookup."""
        super().__init__(client)
        self.names = build_name_lookup(catalogue)

    # -- request construction ------------------------------------------------
    def build_request(
        self,
        sub_function: int = int(DTCSubFunction.REPORT_DTC_BY_STATUS_MASK),
        status_mask: int = MASK_ALL,
        dtc: int | None = None,
        record_number: int | None = None,
        severity_mask: int | None = None,
        memory_selection: int | None = None,
    ) -> bytes:
        """Return the request payload for *sub_function*.

        Raises:
            RequestValidationError: A parameter required by the sub-function is
                missing.
        """
        spec: SubFunctionSpec = describe_sub_function(sub_function)
        payload = bytearray([self.service_id, sub_function & 0xFF])
        if spec.needs_memory_selection:
            if memory_selection is None:
                raise RequestValidationError(f"{spec.label} requires a memory selection byte")
            payload.append(memory_selection & 0xFF)
        if spec.needs_severity_mask:
            if severity_mask is None:
                raise RequestValidationError(f"{spec.label} requires a severity mask")
            payload.append(severity_mask & 0xFF)
        if spec.needs_status_mask:
            payload.append(status_mask & 0xFF)
        if spec.needs_dtc:
            if dtc is None:
                raise RequestValidationError(f"{spec.label} requires a DTC value")
            payload.extend((dtc & 0xFFFFFF).to_bytes(3, "big"))
        if spec.needs_record_number:
            payload.append(0xFF if record_number is None else record_number & 0xFF)
        return bytes(payload)

    # -- response parsing -------------------------------------------------------
    def parse_response(self, response: DiagnosticResponse) -> DTCReport:
        """Parse a 0x59 response into a :class:`DTCReport`.

        Raises:
            InvalidResponseError: The response is negative, missing or short.
        """
        raw = self.require_positive(response, min_length=2)
        sub_function = raw[1]
        spec = describe_sub_function(sub_function)
        report = DTCReport(sub_function=sub_function, raw=raw)
        body = raw[2:]
        if spec.returns_count:
            if len(body) >= 4:
                report.status_availability_mask = body[0]
                report.raw = raw
                report.dtcs = []
                count = int.from_bytes(body[2:4], "big")
                report.raw = raw
                setattr(report, "count", count)  # noqa: B010 - dynamic extra field
            return report
        if body:
            report.status_availability_mask = body[0]
            report.dtcs = parse_dtc_list(body[1:], self.names)
        return report

    # -- high level operations ----------------------------------------------------
    def execute(
        self,
        sub_function: int = int(DTCSubFunction.REPORT_DTC_BY_STATUS_MASK),
        status_mask: int = MASK_ALL,
        **kwargs: int,
    ) -> DTCReport:
        """Send the request and return the parsed report."""
        payload = self.build_request(sub_function, status_mask, **kwargs)
        response = self.send(payload, timeout=3.0)
        report = self.parse_response(response)
        self.client.bus.publish(
            EventType.DIAG_DTC_READ,
            {"sub_function": sub_function, "count": len(report)},
            "ReadDTCInformation",
        )
        return report

    def read_by_status_mask(self, status_mask: int = MASK_ALL) -> DTCReport:
        """Read every DTC matching *status_mask* (sub-function 0x02)."""
        return self.execute(int(DTCSubFunction.REPORT_DTC_BY_STATUS_MASK), status_mask)

    def count_by_status_mask(self, status_mask: int = MASK_ALL) -> int:
        """Return the number of DTCs matching *status_mask* (sub-function 0x01)."""
        payload = self.build_request(
            int(DTCSubFunction.REPORT_NUMBER_OF_DTC_BY_STATUS_MASK), status_mask
        )
        response = self.send(payload, timeout=3.0)
        raw = self.require_positive(response, min_length=6)
        return int.from_bytes(raw[4:6], "big")

    def read_supported(self) -> DTCReport:
        """Read all supported DTCs (sub-function 0x0A)."""
        return self.execute(int(DTCSubFunction.REPORT_SUPPORTED_DTC))

    def read_confirmed(self) -> DTCReport:
        """Read confirmed DTCs using the confirmed status bit."""
        return self.read_by_status_mask(int(StatusMask.from_bits(confirmed=True)))

    def read_pending(self) -> DTCReport:
        """Read pending DTCs using the pending status bit."""
        return self.read_by_status_mask(int(StatusMask.from_bits(pending=True)))

    def read_permanent(self) -> DTCReport:
        """Read DTCs with permanent status (sub-function 0x15)."""
        return self.execute(int(DTCSubFunction.REPORT_DTC_WITH_PERMANENT_STATUS))

    def read_snapshot(self, dtc: int, record_number: int = 0xFF) -> DTC:
        """Read the freeze frame records of *dtc* (sub-function 0x04)."""
        from .dtc_snapshot_reader import DTCSnapshotReader

        return DTCSnapshotReader(self.client).read(dtc, record_number)

    def read_extended(self, dtc: int, record_number: int = 0xFF) -> DTC:
        """Read the extended data records of *dtc* (sub-function 0x06)."""
        from .dtc_extended_reader import DTCExtendedReader

        return DTCExtendedReader(self.client).read(dtc, record_number)


__all__ = ["ReadDTCInformation"]
