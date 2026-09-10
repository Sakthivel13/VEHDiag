"""SecurityAccess - SID 0x27."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable

from ....core.enums.nrc_enums import NegativeResponseCode
from ....core.enums.session_enums import SecurityState
from ....core.enums.sid_enums import ServiceID
from ....core.event_bus import EventType
from ....core.exceptions import RequestValidationError, SecurityAccessDeniedError
from ....core.models.response_data_model import DiagnosticResponse
from ..base_service import BaseService
from .security_algorithms import compute_key
from .security_dll_loader import AlgorithmSource, LoadedAlgorithm, SecurityDLLLoader

_logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SecurityAccessResult:
    """Outcome of a complete unlock attempt."""

    level: int
    unlocked: bool
    seed: bytes = b""
    key: bytes = b""
    attempts: int = 0
    delay_remaining_s: float = 0.0
    message: str = ""
    responses: list[DiagnosticResponse] = field(default_factory=list)

    @property
    def already_unlocked(self) -> bool:
        """Return ``True`` when the ECU answered with an all-zero seed."""
        return bool(self.seed) and not any(self.seed)

    def __str__(self) -> str:  # noqa: D105 - trivial
        state = "unlocked" if self.unlocked else "locked"
        return f"security level 0x{self.level:02X} {state}: {self.message}"


class SecurityAccess(BaseService):
    """Request a seed and submit the derived key to unlock the ECU.

    Args:
        client: UDS client used for transmission.
        algorithm: Name of a built-in algorithm.
        algorithm_params: Parameters forwarded to the built-in algorithm.
        external: A previously loaded external algorithm.
    """

    service_id = int(ServiceID.SECURITY_ACCESS)
    min_request_length = 2
    has_sub_function = True

    def __init__(
        self,
        client,  # noqa: ANN001
        algorithm: str = "xor_complement",
        algorithm_params: dict[str, object] | None = None,
        external: LoadedAlgorithm | None = None,
    ) -> None:
        """Store the client and the algorithm configuration."""
        super().__init__(client)
        self.algorithm = algorithm
        self.algorithm_params = algorithm_params or {}
        self.external = external
        self.loader = SecurityDLLLoader()
        self.attempts = 0
        self.delay_until = 0.0

    # -- request construction ------------------------------------------------
    def build_request(self, level: int, key: bytes = b"") -> bytes:
        """Return ``27 <level> [key]``.

        Raises:
            RequestValidationError: The level is outside 0x01..0x7E.
        """
        if not 0x01 <= level <= 0x7E:
            raise RequestValidationError(
                "the security level must be in 0x01..0x7E", {"value": f"0x{level:02X}"}
            )
        return bytes([self.service_id, level & 0xFF]) + key

    def parse_response(self, response: DiagnosticResponse) -> bytes:
        """Return the seed carried by a positive seed response."""
        raw = self.require_positive(response, min_length=2)
        return bytes(raw[2:])

    # -- individual steps -------------------------------------------------------
    def request_seed(self, level: int = 0x01) -> bytes:
        """Request the seed for an odd security *level*."""
        response = self.send(self.build_request(level))
        if response.is_negative:
            self._handle_negative(response)
        return self.parse_response(response)

    def send_key(self, level: int, key: bytes) -> bool:
        """Submit *key* for the even sub-function of *level*."""
        response = self.send(self.build_request(level + 1, key))
        if response.is_negative:
            self._handle_negative(response)
            return False
        self.client.state.apply_unlock(level + 1)
        self.attempts = 0
        self.client.bus.publish(
            EventType.DIAG_SECURITY_UNLOCKED, {"level": level}, "SecurityAccess"
        )
        return True

    def compute(self, seed: bytes, level: int = 0x01) -> bytes:
        """Derive the key from *seed* using the configured algorithm."""
        if self.external is not None:
            return self.external(seed, level)
        return compute_key(self.algorithm, seed, self.algorithm_params)

    # -- orchestration -------------------------------------------------------------
    def execute(self, level: int = 0x01, key: bytes | None = None) -> SecurityAccessResult:
        """Perform the full seed request / key submission sequence.

        Args:
            level: Odd security level to unlock.
            key: Manually supplied key; when ``None`` the key is computed.

        Returns:
            The :class:`SecurityAccessResult` describing the attempt.
        """
        result = SecurityAccessResult(level=level, unlocked=False)
        remaining = self.delay_remaining()
        if remaining > 0:
            result.delay_remaining_s = remaining
            result.message = f"security delay active, {remaining:.1f} s remaining"
            return result

        seed_response = self.send(self.build_request(level))
        result.responses.append(seed_response)
        if seed_response.is_negative:
            self._handle_negative(seed_response)
            result.message = seed_response.nrc_text
            return result
        result.seed = bytes(seed_response.raw[2:])

        if result.already_unlocked:
            result.unlocked = True
            result.message = "the ECU reported an all-zero seed; already unlocked"
            self.client.state.apply_unlock(level + 1)
            return result

        try:
            result.key = key if key is not None else self.compute(result.seed, level)
        except Exception as exc:  # noqa: BLE001 - algorithm errors are user facing
            result.message = f"key computation failed: {exc}"
            return result

        key_response = self.send(self.build_request(level + 1, result.key))
        result.responses.append(key_response)
        self.attempts += 1
        result.attempts = self.attempts
        if key_response.is_positive():
            result.unlocked = True
            result.message = "unlocked"
            self.attempts = 0
            self.client.state.apply_unlock(level + 1)
            self.client.bus.publish(
                EventType.DIAG_SECURITY_UNLOCKED, {"level": level}, "SecurityAccess"
            )
        else:
            self._handle_negative(key_response)
            result.message = key_response.nrc_text
            self.client.bus.publish(
                EventType.DIAG_SECURITY_FAILED,
                {"level": level, "nrc": key_response.nrc},
                "SecurityAccess",
            )
        _logger.info("%s", result)
        return result

    def unlock(self, level: int = 0x01) -> bool:
        """Unlock *level* and return whether the ECU accepted the key.

        Raises:
            SecurityAccessDeniedError: The ECU refused the unlock attempt.
        """
        result = self.execute(level)
        if not result.unlocked:
            raise SecurityAccessDeniedError(
                f"could not unlock security level 0x{level:02X}", {"reason": result.message}
            )
        return True

    # -- helpers -------------------------------------------------------------------
    def load_external(self, path: str, **kwargs: object) -> LoadedAlgorithm:
        """Load an external DLL/SO or Python seed-key implementation."""
        self.external = self.loader.load(path, **kwargs)
        return self.external

    def use_builtin(self, algorithm: str, params: dict[str, object] | None = None) -> None:
        """Switch back to one of the built-in algorithms."""
        self.external = None
        self.algorithm = algorithm
        self.algorithm_params = params or {}

    def delay_remaining(self) -> float:
        """Return the remaining security delay in seconds."""
        return max(0.0, self.delay_until - time.time())

    @property
    def source(self) -> AlgorithmSource:
        """Return where the active algorithm comes from."""
        return self.external.source if self.external is not None else AlgorithmSource.BUILTIN

    def _handle_negative(self, response: DiagnosticResponse) -> None:
        """Update the attempt counter and the delay timer from an NRC."""
        nrc = response.nrc
        self.client.state.security_state = SecurityState.LOCKED
        if nrc == int(NegativeResponseCode.EXCEEDED_NUMBER_OF_ATTEMPTS):
            self.delay_until = time.time() + 10.0
            self.client.state.security_state = SecurityState.DELAY_ACTIVE
        elif nrc == int(NegativeResponseCode.REQUIRED_TIME_DELAY_NOT_EXPIRED):
            self.delay_until = max(self.delay_until, time.time() + 5.0)
            self.client.state.security_state = SecurityState.DELAY_ACTIVE


__all__ = ["SecurityAccess", "SecurityAccessResult"]
