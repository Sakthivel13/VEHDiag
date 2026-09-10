"""RequestFileTransfer - SID 0x38."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import IntEnum

from ....core.enums.sid_enums import ServiceID
from ....core.enums.transfer_enums import (
    CompressionMethod,
    EncryptionMethod,
    data_format_identifier,
)
from ....core.exceptions import RequestValidationError
from ....core.models.response_data_model import DiagnosticResponse
from ..base_service import BaseService

_logger = logging.getLogger(__name__)


class FileOperation(IntEnum):
    """modeOfOperation values of RequestFileTransfer."""

    ADD_FILE = 0x01
    DELETE_FILE = 0x02
    REPLACE_FILE = 0x03
    READ_FILE = 0x04
    READ_DIRECTORY = 0x05
    RESUME_FILE = 0x06


@dataclass(slots=True)
class FileTransferPermission:
    """The ECU answer to a file transfer request."""

    operation: int
    max_block_length: int = 0
    file_size_uncompressed: int = 0
    file_size_compressed: int = 0
    raw: bytes = b""

    @property
    def max_payload(self) -> int:
        """Return the usable payload per TransferData request."""
        return max(1, self.max_block_length - 2)


class RequestFileTransfer(BaseService):
    """Perform file system operations on the ECU."""

    service_id = int(ServiceID.REQUEST_FILE_TRANSFER)
    min_request_length = 4
    has_sub_function = False

    def build_request(
        self,
        operation: int,
        file_path: str,
        file_size_uncompressed: int = 0,
        file_size_compressed: int = 0,
        compression: CompressionMethod = CompressionMethod.NONE,
        encryption: EncryptionMethod = EncryptionMethod.NONE,
        size_bytes: int = 4,
    ) -> bytes:
        """Return the RequestFileTransfer payload.

        Raises:
            RequestValidationError: The path is empty or the operation unknown.
        """
        if not file_path:
            raise RequestValidationError("RequestFileTransfer needs a file path")
        try:
            mode = FileOperation(operation)
        except ValueError as exc:
            raise RequestValidationError(
                "unknown modeOfOperation", {"value": f"0x{operation:02X}"}
            ) from exc
        encoded = file_path.encode("utf-8")
        payload = bytearray([self.service_id, int(mode)])
        payload.extend(len(encoded).to_bytes(2, "big"))
        payload.extend(encoded)
        if mode in (FileOperation.ADD_FILE, FileOperation.REPLACE_FILE, FileOperation.RESUME_FILE):
            payload.append(data_format_identifier(compression, encryption))
            payload.append(size_bytes & 0xFF)
            payload.extend(file_size_uncompressed.to_bytes(size_bytes, "big"))
            payload.extend(file_size_compressed.to_bytes(size_bytes, "big"))
        elif mode is FileOperation.READ_FILE:
            payload.append(data_format_identifier(compression, encryption))
        return bytes(payload)

    def parse_response(self, response: DiagnosticResponse) -> FileTransferPermission:
        """Parse the mode echo and the block length information."""
        raw = self.require_positive(response, min_length=2)
        permission = FileTransferPermission(operation=raw[1], raw=raw)
        if len(raw) < 3:
            return permission
        length_format = raw[2]
        offset = 3
        if length_format and len(raw) >= offset + length_format:
            permission.max_block_length = int.from_bytes(raw[offset : offset + length_format], "big")
            offset += length_format
        if len(raw) > offset + 1:
            size_bytes = raw[offset + 1]
            offset += 2
            if len(raw) >= offset + size_bytes:
                permission.file_size_uncompressed = int.from_bytes(
                    raw[offset : offset + size_bytes], "big"
                )
        return permission

    def execute(self, operation: int, file_path: str, **kwargs: object) -> FileTransferPermission:
        """Send one file transfer request."""
        payload = self.build_request(operation, file_path, **kwargs)  # type: ignore[arg-type]
        return self.parse_response(self.send(payload, timeout=10.0))

    def add_file(self, file_path: str, size: int) -> FileTransferPermission:
        """Create a new file of *size* bytes on the ECU."""
        return self.execute(int(FileOperation.ADD_FILE), file_path, file_size_uncompressed=size)

    def delete_file(self, file_path: str) -> FileTransferPermission:
        """Delete a file from the ECU file system."""
        return self.execute(int(FileOperation.DELETE_FILE), file_path)

    def read_file(self, file_path: str) -> FileTransferPermission:
        """Start reading a file from the ECU."""
        return self.execute(int(FileOperation.READ_FILE), file_path)

    def read_directory(self, path: str = "/") -> FileTransferPermission:
        """List the content of an ECU directory."""
        return self.execute(int(FileOperation.READ_DIRECTORY), path)


__all__ = ["RequestFileTransfer", "FileOperation", "FileTransferPermission"]
