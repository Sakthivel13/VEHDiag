"""Negative Response Code interpretation and retry policy."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from ..core.enums.nrc_enums import RETRYABLE_NRCS, NegativeResponseCode, describe_nrc
from ..core.enums.sid_enums import NEGATIVE_RESPONSE_SID
from ..core.models.response_data_model import DiagnosticResponse

_logger = logging.getLogger(__name__)


@dataclass(slots=True)
class NRCInfo:
    """Everything the UI needs to present a negative response.

    Attributes:
        code: The raw NRC byte.
        name: ISO style lowerCamelCase name.
        description: Explanation of the cause.
        recovery: Suggested corrective action.
        retryable: The request may be retried automatically.
        pending: The code is ``0x78`` responsePending.
    """

    code: int
    name: str
    description: str
    recovery: str
    retryable: bool = False
    pending: bool = False

    @property
    def summary(self) -> str:
        """Return ``"0x33 securityAccessDenied"``."""
        return f"0x{self.code:02X} {self.name}"

    def __str__(self) -> str:  # noqa: D105 - trivial
        return f"{self.summary} - {self.description}"


class NRCHandler:
    """Interpret negative responses and decide whether to retry.

    Args:
        max_retries: How often a retryable NRC may be retried.
        custom_descriptions: OEM specific descriptions keyed by NRC value.
    """

    def __init__(
        self,
        max_retries: int = 3,
        custom_descriptions: dict[int, dict[str, str]] | None = None,
    ) -> None:
        """Create the handler."""
        self.max_retries = max_retries
        self.custom = custom_descriptions or {}
        self.counters: dict[int, int] = {}

    def describe(self, nrc: int) -> NRCInfo:
        """Return the :class:`NRCInfo` for *nrc*.

        Example:
            >>> NRCHandler().describe(0x33).name
            'securityAccessDenied'
        """
        override = self.custom.get(nrc, {})
        code = NegativeResponseCode.from_byte(nrc)
        if code is None:
            return NRCInfo(
                code=nrc,
                name=str(override.get("name", "manufacturerSpecific")),
                description=str(
                    override.get("description", "Manufacturer specific or reserved code.")
                ),
                recovery=str(override.get("recovery", "Consult the OEM documentation.")),
            )
        return NRCInfo(
            code=nrc,
            name=str(override.get("name", code.pretty_name)),
            description=str(override.get("description", code.description)),
            recovery=str(override.get("recovery", code.recovery_hint)),
            retryable=nrc in RETRYABLE_NRCS,
            pending=nrc == int(NegativeResponseCode.REQUEST_CORRECTLY_RECEIVED_RESPONSE_PENDING),
        )

    def analyse(self, response: DiagnosticResponse) -> NRCInfo | None:
        """Return the :class:`NRCInfo` of *response*, or ``None`` when positive."""
        if not response.is_negative:
            return None
        return self.describe(response.raw[2])

    def should_retry(self, nrc: int, attempt: int) -> bool:
        """Return ``True`` when an automatic retry is appropriate.

        Args:
            nrc: The received negative response code.
            attempt: The number of attempts already made (1 based).
        """
        if attempt >= self.max_retries:
            return False
        return nrc in RETRYABLE_NRCS

    def record(self, nrc: int) -> int:
        """Count an occurrence of *nrc* and return the new total."""
        self.counters[nrc] = self.counters.get(nrc, 0) + 1
        return self.counters[nrc]

    def reset_counters(self) -> None:
        """Clear the per-NRC occurrence counters."""
        self.counters.clear()

    @staticmethod
    def build_negative_response(service_id: int, nrc: int) -> bytes:
        """Return the raw bytes of a negative response (used by simulators)."""
        return bytes([NEGATIVE_RESPONSE_SID, service_id & 0xFF, nrc & 0xFF])

    @staticmethod
    def format(nrc: int) -> str:
        """Return the standard one line description of *nrc*."""
        return describe_nrc(nrc)


__all__ = ["NRCHandler", "NRCInfo"]
