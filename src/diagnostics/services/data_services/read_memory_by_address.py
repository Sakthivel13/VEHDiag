"""ReadMemoryByAddress - SID 0x23."""
from __future__ import annotations

import logging

from ....core.enums.sid_enums import ServiceID
from ....core.exceptions import RequestValidationError
from ....core.models.response_data_model import DiagnosticResponse
from ..base_service import BaseService

_logger = logging.getLogger(__name__)


def build_address_length_format(address_bytes: int, length_bytes: int) -> int:
    """Return the addressAndLengthFormatIdentifier byte.

    Example:
        >>> hex(build_address_length_format(4, 2))
        '0x24'
    """
    return ((length_bytes & 0x0F) << 4) | (address_bytes & 0x0F)


class ReadMemoryByAddress(BaseService):
    """Read a block of ECU memory by physical address."""

    service_id = int(ServiceID.READ_MEMORY_BY_ADDRESS)
    min_request_length = 4
    has_sub_function = False

    def build_request(
        self,
        address: int,
        size: int,
        address_bytes: int = 4,
        length_bytes: int = 2,
    ) -> bytes:
        """Return ``23 <alfid> <address> <size>``.

        Raises:
            RequestValidationError: The address or size does not fit into the
                configured number of bytes.
        """
        if not 1 <= address_bytes <= 8 or not 1 <= length_bytes <= 8:
            raise RequestValidationError("address and length widths must be 1..8 bytes")
        if address >= (1 << (address_bytes * 8)):
            raise RequestValidationError(
                f"address 0x{address:X} does not fit into {address_bytes} bytes"
            )
        if size >= (1 << (length_bytes * 8)):
            raise RequestValidationError(f"size {size} does not fit into {length_bytes} bytes")
        return (
            bytes([self.service_id, build_address_length_format(address_bytes, length_bytes)])
            + address.to_bytes(address_bytes, "big")
            + size.to_bytes(length_bytes, "big")
        )

    def parse_response(self, response: DiagnosticResponse) -> bytes:
        """Return the memory content carried by the response."""
        raw = self.require_positive(response, min_length=2)
        return bytes(raw[1:])

    def execute(
        self,
        address: int,
        size: int,
        address_bytes: int = 4,
        length_bytes: int = 2,
    ) -> bytes:
        """Read *size* bytes starting at *address*."""
        payload = self.build_request(address, size, address_bytes, length_bytes)
        return self.parse_response(self.send(payload, timeout=3.0))

    def read_blocks(self, address: int, size: int, block_size: int = 0x100) -> bytes:
        """Read a large region in blocks of *block_size* bytes."""
        data = bytearray()
        remaining = size
        cursor = address
        while remaining > 0:
            chunk = min(block_size, remaining)
            data.extend(self.execute(cursor, chunk))
            cursor += chunk
            remaining -= chunk
        return bytes(data)


__all__ = ["ReadMemoryByAddress", "build_address_length_format"]
