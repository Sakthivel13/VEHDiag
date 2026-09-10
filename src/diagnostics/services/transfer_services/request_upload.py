"""RequestUpload - SID 0x35."""
from __future__ import annotations

import logging

from ....core.enums.sid_enums import ServiceID
from ....core.enums.transfer_enums import CompressionMethod, EncryptionMethod
from ....core.models.response_data_model import DiagnosticResponse
from ..base_service import BaseService
from .request_download import DownloadPermission, RequestDownload

_logger = logging.getLogger(__name__)


class RequestUpload(RequestDownload):
    """Announce an upload of data from ECU memory.

    The request layout is identical to :class:`RequestDownload`; only the
    direction and the service identifier differ.
    """

    service_id = int(ServiceID.REQUEST_UPLOAD)

    def execute(
        self,
        address: int,
        size: int,
        address_bytes: int = 4,
        length_bytes: int = 4,
        compression: CompressionMethod = CompressionMethod.NONE,
        encryption: EncryptionMethod = EncryptionMethod.NONE,
    ) -> DownloadPermission:
        """Request permission to upload *size* bytes from *address*."""
        payload = self.build_request(
            address, size, address_bytes, length_bytes, compression, encryption
        )
        permission = self.parse_response(self.send(payload, timeout=10.0))
        _logger.info(
            "upload accepted from 0x%08X, max block length %d", address, permission.max_block_length
        )
        return permission


__all__ = ["RequestUpload"]
