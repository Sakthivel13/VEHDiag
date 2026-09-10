"""ClearDiagnosticInformation - SID 0x14."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from ....core.enums.sid_enums import ServiceID
from ....core.event_bus import EventType
from ....core.exceptions import RequestValidationError
from ....core.models.dtc_model import DTCReport
from ....core.models.response_data_model import DiagnosticResponse
from ..base_service import BaseService
from .dtc_parser import group_mask
from .read_dtc_information import ReadDTCInformation

_logger = logging.getLogger(__name__)

#: Value clearing every stored DTC.
CLEAR_ALL = 0xFFFFFF


@dataclass(slots=True)
class ClearResult:
    """Outcome of a clear operation including the before/after comparison."""

    group: int
    accepted: bool
    before: DTCReport | None = None
    after: DTCReport | None = None
    response: DiagnosticResponse | None = None

    @property
    def cleared_count(self) -> int:
        """Return how many DTCs disappeared."""
        if self.before is None or self.after is None:
            return 0
        return max(0, len(self.before) - len(self.after))

    @property
    def summary(self) -> str:
        """Return a one line description for the log and the UI."""
        if not self.accepted:
            reason = self.response.nrc_text if self.response else "no response"
            return f"clear rejected: {reason}"
        if self.before is None:
            return "DTCs cleared"
        return f"cleared {self.cleared_count} of {len(self.before)} DTCs"


class ClearDiagnosticInformation(BaseService):
    """Clear stored diagnostic trouble codes."""

    service_id = int(ServiceID.CLEAR_DIAGNOSTIC_INFORMATION)
    min_request_length = 4
    has_sub_function = False

    def build_request(self, group: int = CLEAR_ALL, memory_selection: int | None = None) -> bytes:
        """Return ``14 <group hi> <group mid> <group lo> [memory]``.

        Raises:
            RequestValidationError: The group is outside the 24-bit range.
        """
        if not 0 <= group <= 0xFFFFFF:
            raise RequestValidationError(
                "the DTC group must fit into three bytes", {"value": hex(group)}
            )
        payload = bytes([self.service_id]) + group.to_bytes(3, "big")
        if memory_selection is not None:
            payload += bytes([memory_selection & 0xFF])
        return payload

    def parse_response(self, response: DiagnosticResponse) -> bool:
        """Return ``True`` when the ECU accepted the clear request."""
        return response.is_positive()

    def execute(
        self,
        group: int | str = CLEAR_ALL,
        memory_selection: int | None = None,
        verify: bool = True,
    ) -> ClearResult:
        """Clear DTCs and optionally read them before and after.

        Args:
            group: Numeric group value or a group name such as ``"powertrain"``.
            memory_selection: Optional user defined memory selector.
            verify: Read the DTC list before and after the clear operation.

        Returns:
            The :class:`ClearResult` describing the operation.
        """
        value = group_mask(group) if isinstance(group, str) else int(group)
        reader = ReadDTCInformation(self.client) if verify else None
        before = None
        if reader is not None:
            try:
                before = reader.read_by_status_mask()
            except Exception:  # noqa: BLE001 - verification is best effort
                _logger.debug("pre-clear DTC read failed", exc_info=True)

        response = self.send(self.build_request(value, memory_selection), timeout=5.0)
        accepted = self.parse_response(response)

        after = None
        if reader is not None and accepted:
            try:
                after = reader.read_by_status_mask()
            except Exception:  # noqa: BLE001
                _logger.debug("post-clear DTC read failed", exc_info=True)

        result = ClearResult(value, accepted, before, after, response)
        if accepted:
            self.client.bus.publish(
                EventType.DIAG_DTC_CLEARED,
                {"group": value, "cleared": result.cleared_count},
                "ClearDiagnosticInformation",
            )
        _logger.info("%s", result.summary)
        return result

    def clear_all(self, verify: bool = True) -> ClearResult:
        """Clear every DTC (group ``0xFFFFFF``)."""
        return self.execute(CLEAR_ALL, verify=verify)

    def clear_group(self, name: str, verify: bool = True) -> ClearResult:
        """Clear one named group (powertrain, chassis, body, network)."""
        return self.execute(name, verify=verify)


__all__ = ["ClearDiagnosticInformation", "ClearResult", "CLEAR_ALL"]
