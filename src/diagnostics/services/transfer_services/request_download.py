"""RequestDownload - SID 0x34."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from ....core.enums.sid_enums import ServiceID
from ....core.enums.transfer_enums import (
    CompressionMethod,
    EncryptionMethod,
    data_format_identifier,
)
from ....core.exceptions import RequestValidationError, TransferError
from ....core.models.response_data_model import DiagnosticResponse
from ..base_service import BaseService

_logger = logging.getLogger(__name__)


@dataclass(slots=True)
class DownloadPermission:
    """The ECU answer to a download request.

    Attributes:
        max_block_length: Largest TransferData request the ECU accepts,
            including the SID and the block sequence counter.
        raw: The raw response payload.
    """

    max_block_length: int
    raw: bytes = b""

    @property
    def max_payload(self) -> int:
        """Return the usable payload per TransferData request."""
        return max(1, self.max_block_length - 2)


class RequestDownload(BaseService):
    """Announce a download of data into ECU memory."""

    service_id = int(ServiceID.REQUEST_DOWNLOAD)
    min_request_length = 3
    has_sub_function = False

    def build_request(
        self,
        address: int,
        size: int,
        address_bytes: int = 4,
        length_bytes: int = 4,
        compression: CompressionMethod = CompressionMethod.NONE,
        encryption: EncryptionMethod = EncryptionMethod.NONE,
    ) -> bytes:
        """Return ``34 <dfi> <alfid> <address> <size>``.

        Raises:
            RequestValidationError: The address or size does not fit.
        """
        if address >= (1 << (address_bytes * 8)):
            raise RequestValidationError(
                f"address 0x{address:X} does not fit into {address_bytes} bytes"
            )
        if size >= (1 << (length_bytes * 8)):
            raise RequestValidationError(f"size {size} does not fit into {length_bytes} bytes")
        alfid = ((length_bytes & 0x0F) << 4) | (address_bytes & 0x0F)
        return (
            bytes([self.service_id, data_format_identifier(compression, encryption), alfid])
            + address.to_bytes(address_bytes, "big")
            + size.to_bytes(length_bytes, "big")
        )

    def parse_response(self, response: DiagnosticResponse) -> DownloadPermission:
        """Extract the maxNumberOfBlockLength value.

        Raises:
            TransferError: The response is malformed.
        """
        raw = self.require_positive(response, min_length=2)
        length_format = (raw[1] >> 4) & 0x0F
        if length_format == 0 or len(raw) < 2 + length_format:
            raise TransferError(
                "malformed RequestDownload response", {"raw": raw.hex(" ").upper()}
            )
        max_block = int.from_bytes(raw[2 : 2 + length_format], "big")
        return DownloadPermission(max_block_length=max_block, raw=raw)

    def execute(
        self,
        address: int,
        size: int,
        address_bytes: int = 4,
        length_bytes: int = 4,
        compression: CompressionMethod = CompressionMethod.NONE,
        encryption: EncryptionMethod = EncryptionMethod.NONE,
    ) -> DownloadPermission:
        """Request permission to download *size* bytes to *address*."""
        payload = self.build_request(
            address, size, address_bytes, length_bytes, compression, encryption
        )
        permission = self.parse_response(self.send(payload, timeout=10.0))
        _logger.info(
            "download accepted at 0x%08X, max block length %d", address, permission.max_block_length
        )
        return permission


__all__ = ["RequestDownload", "DownloadPermission"]
