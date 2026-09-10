"""WriteDataByIdentifier - SID 0x2E."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from ....core.enums.sid_enums import ServiceID
from ....core.exceptions import RequestValidationError
from ....core.models.did_model import DIDRegistry, DIDValue
from ....core.models.response_data_model import DiagnosticResponse
from ..base_service import BaseService
from .read_data_by_id import ReadDataByIdentifier

_logger = logging.getLogger(__name__)


@dataclass(slots=True)
class WriteResult:
    """Outcome of a write operation including the verification read."""

    did: int
    accepted: bool
    before: DIDValue | None = None
    after: DIDValue | None = None
    response: DiagnosticResponse | None = None

    @property
    def verified(self) -> bool:
        """Return ``True`` when the read-back matches the written data."""
        return self.after is not None and self.accepted

    @property
    def summary(self) -> str:
        """Return a one line description of the operation."""
        if not self.accepted:
            reason = self.response.nrc_text if self.response else "no response"
            return f"write to 0x{self.did:04X} rejected: {reason}"
        state = "verified" if self.verified else "not verified"
        return f"write to 0x{self.did:04X} accepted ({state})"


class WriteDataByIdentifier(BaseService):
    """Write a data record identified by a DID.

    Args:
        client: UDS client used for transmission.
        registry: DID definitions used to validate the payload length.
    """

    service_id = int(ServiceID.WRITE_DATA_BY_IDENTIFIER)
    min_request_length = 4
    has_sub_function = False

    def __init__(self, client, registry: DIDRegistry | None = None) -> None:  # noqa: ANN001
        """Store the client and the DID registry."""
        super().__init__(client)
        self.registry = registry or DIDRegistry()

    def build_request(self, did: int, data: bytes) -> bytes:
        """Return ``2E <did hi> <did lo> <data>``.

        Raises:
            RequestValidationError: The DID is out of range, the data is empty
                or its length contradicts the known definition.
        """
        if not 0 <= did <= 0xFFFF:
            raise RequestValidationError("the data identifier must fit into two bytes")
        if not data:
            raise RequestValidationError("WriteDataByIdentifier requires at least one data byte")
        definition = self.registry.get(did)
        if definition is not None and definition.length and len(data) != definition.length:
            raise RequestValidationError(
                f"DID 0x{did:04X} expects {definition.length} bytes",
                {"received": len(data)},
            )
        return bytes([self.service_id]) + did.to_bytes(2, "big") + data

    def parse_response(self, response: DiagnosticResponse) -> bool:
        """Return ``True`` when the ECU echoed the identifier positively."""
        return response.is_positive()

    def execute(self, did: int, data: bytes, verify: bool = True) -> WriteResult:
        """Write *data* to *did*, optionally reading before and after."""
        reader = ReadDataByIdentifier(self.client, self.registry) if verify else None
        before = reader.read_one(did) if reader is not None else None
        response = self.send(self.build_request(did, data))
        accepted = self.parse_response(response)
        after = reader.read_one(did) if (reader is not None and accepted) else None
        result = WriteResult(did, accepted, before, after, response)
        _logger.info("%s", result.summary)
        return result

    def write_ascii(self, did: int, text: str, verify: bool = True) -> WriteResult:
        """Write an ASCII string to *did*."""
        return self.execute(did, text.encode("ascii"), verify)


__all__ = ["WriteDataByIdentifier", "WriteResult"]
