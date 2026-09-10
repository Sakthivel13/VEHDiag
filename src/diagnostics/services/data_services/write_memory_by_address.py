"""WriteMemoryByAddress - SID 0x3D."""
from __future__ import annotations

import logging

from ....core.enums.sid_enums import ServiceID
from ....core.exceptions import RequestValidationError
from ....core.models.response_data_model import DiagnosticResponse
from ..base_service import BaseService
from .read_memory_by_address import build_address_length_format

_logger = logging.getLogger(__name__)


class WriteMemoryByAddress(BaseService):
    """Write a block of ECU memory by physical address."""

    service_id = int(ServiceID.WRITE_MEMORY_BY_ADDRESS)
    min_request_length = 5
    has_sub_function = False

    def build_request(
        self,
        address: int,
        data: bytes,
        address_bytes: int = 4,
        length_bytes: int = 2,
    ) -> bytes:
        """Return ``3D <alfid> <address> <size> <data>``.

        Raises:
            RequestValidationError: The data is empty or the address does not
                fit into the configured width.
        """
        if not data:
            raise RequestValidationError("WriteMemoryByAddress requires data to write")
        if address >= (1 << (address_bytes * 8)):
            raise RequestValidationError(
                f"address 0x{address:X} does not fit into {address_bytes} bytes"
            )
        return (
            bytes([self.service_id, build_address_length_format(address_bytes, length_bytes)])
            + address.to_bytes(address_bytes, "big")
            + len(data).to_bytes(length_bytes, "big")
            + data
        )

    def parse_response(self, response: DiagnosticResponse) -> bool:
        """Return ``True`` when the ECU accepted the write."""
        return response.is_positive()

    def execute(
        self,
        address: int,
        data: bytes,
        address_bytes: int = 4,
        length_bytes: int = 2,
    ) -> bool:
        """Write *data* to *address*."""
        payload = self.build_request(address, data, address_bytes, length_bytes)
        return self.parse_response(self.send(payload, timeout=5.0))


__all__ = ["WriteMemoryByAddress"]
