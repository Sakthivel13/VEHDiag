"""TransferData - SID 0x36."""
from __future__ import annotations

import logging

from ....core.enums.sid_enums import ServiceID
from ....core.exceptions import RequestValidationError, TransferError
from ....core.models.response_data_model import DiagnosticResponse
from ..base_service import BaseService
from .block_sequence_counter import BlockSequenceCounter

_logger = logging.getLogger(__name__)


class TransferData(BaseService):
    """Transfer one data block during an upload or download.

    Args:
        client: UDS client used for transmission.
        counter: Shared block sequence counter (created when omitted).
    """

    service_id = int(ServiceID.TRANSFER_DATA)
    min_request_length = 2
    has_sub_function = False

    def __init__(self, client, counter: BlockSequenceCounter | None = None) -> None:  # noqa: ANN001
        """Store the client and the block sequence counter."""
        super().__init__(client)
        self.counter = counter or BlockSequenceCounter()

    def build_request(self, block_number: int, data: bytes = b"") -> bytes:
        """Return ``36 <block> <data>``.

        Raises:
            RequestValidationError: The block number exceeds one byte.
        """
        if not 0 <= block_number <= 0xFF:
            raise RequestValidationError("the block sequence counter is a single byte")
        return bytes([self.service_id, block_number & 0xFF]) + data

    def parse_response(self, response: DiagnosticResponse) -> int:
        """Return the block sequence counter echoed by the ECU.

        Raises:
            TransferError: The ECU rejected the block.
        """
        if response.is_negative:
            raise TransferError(
                f"TransferData rejected: {response.nrc_text}", {"nrc": response.nrc}
            )
        raw = self.require_positive(response, min_length=2)
        return raw[1]

    def send_block(self, data: bytes, timeout: float = 5.0) -> int:
        """Send the next block and verify the echoed counter.

        Returns:
            The block number that was transmitted.

        Raises:
            TransferError: The ECU echoed a wrong counter or rejected the block.
        """
        block_number = self.counter.next()
        payload = self.build_request(block_number, data)
        try:
            echoed = self.parse_response(self.send(payload, timeout=timeout))
        except TransferError:
            self.counter.rollback()
            raise
        self.counter.verify(echoed)
        return block_number

    def retry_block(self, data: bytes, timeout: float = 5.0) -> int:
        """Resend the current block without advancing the counter."""
        payload = self.build_request(self.counter.value, data)
        echoed = self.parse_response(self.send(payload, timeout=timeout))
        self.counter.verify(echoed)
        return self.counter.value

    def receive_block(self, timeout: float = 5.0) -> bytes:
        """Request the next block during an upload and return its payload."""
        block_number = self.counter.next()
        payload = self.build_request(block_number)
        response = self.send(payload, timeout=timeout)
        raw = self.require_positive(response, min_length=2)
        self.counter.verify(raw[1])
        return bytes(raw[2:])

    def reset(self) -> None:
        """Reset the block sequence counter."""
        self.counter.reset()

    def execute(self, data: bytes) -> int:
        """Alias of :meth:`send_block` satisfying the service interface."""
        return self.send_block(data)


__all__ = ["TransferData"]
