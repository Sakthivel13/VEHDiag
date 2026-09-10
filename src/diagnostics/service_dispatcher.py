"""Routing of diagnostic requests to their service implementation."""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable

from ..core.enums.sid_enums import (
    NON_DEFAULT_SESSION_SERVICES,
    SECURITY_REQUIRED_SERVICES,
    ServiceID,
)
from ..core.enums.session_enums import SecurityState, SessionType
from ..core.exceptions import (
    SecurityAccessDeniedError,
    ServiceNotSupportedError,
    SessionNotSupportedError,
)
from ..core.interfaces.i_diagnostic_service import IDiagnosticService
from .uds_client import UDSClient

_logger = logging.getLogger(__name__)


@dataclass(slots=True)
class DispatchRecord:
    """One entry of the dispatcher execution log."""

    service_id: int
    name: str
    arguments: tuple[Any, ...] = ()
    succeeded: bool = True
    error: str = ""
    duration_ms: float = 0.0


class ServiceDispatcher:
    """Creates, caches and executes the diagnostic service objects.

    The dispatcher gives the UI and the test runner one entry point:
    ``dispatcher.execute(0x22, 0xF190)`` instead of importing every service
    class explicitly.

    Args:
        client: The UDS client shared by all services.
        validate_preconditions: Refuse requests the current session forbids.
    """

    def __init__(self, client: UDSClient, validate_preconditions: bool = False) -> None:
        """Create the dispatcher with an empty service cache."""
        self.client = client
        self.validate_preconditions = validate_preconditions
        self.history: list[DispatchRecord] = []
        self._services: dict[int, IDiagnosticService] = {}
        self._factories: dict[int, Callable[[UDSClient], IDiagnosticService]] = {}
        self._lock = threading.RLock()
        self._register_builtin()

    # -- registration -------------------------------------------------------
    def _register_builtin(self) -> None:
        """Register the factory of every bundled service."""
        from .services.communication_control.communication_control import CommunicationControl
        from .services.communication_control.link_control import LinkControl
        from .services.communication_control.response_on_event import ResponseOnEvent
        from .services.data_services.dynamic_define_did import DynamicallyDefineDataIdentifier
        from .services.data_services.read_data_by_id import ReadDataByIdentifier
        from .services.data_services.read_memory_by_address import ReadMemoryByAddress
        from .services.data_services.read_periodic_data import ReadDataByPeriodicIdentifier
        from .services.data_services.read_scaling_data import ReadScalingDataByIdentifier
        from .services.data_services.write_data_by_id import WriteDataByIdentifier
        from .services.data_services.write_memory_by_address import WriteMemoryByAddress
        from .services.dtc_services.clear_dtc import ClearDiagnosticInformation
        from .services.dtc_services.control_dtc_setting import ControlDTCSetting
        from .services.dtc_services.read_dtc_information import ReadDTCInformation
        from .services.ecu_reset.ecu_reset_service import ECUReset
        from .services.io_control.io_control_by_id import InputOutputControlByIdentifier
        from .services.misc_services.access_timing_parameter import AccessTimingParameter
        from .services.misc_services.tester_present import TesterPresent
        from .services.routine_control.routine_control import RoutineControl
        from .services.security.authentication import Authentication
        from .services.security.secured_data_transmission import SecuredDataTransmission
        from .services.security.security_access import SecurityAccess
        from .services.session_control.diagnostic_session_control import DiagnosticSessionControl
        from .services.transfer_services.request_download import RequestDownload
        from .services.transfer_services.request_file_transfer import RequestFileTransfer
        from .services.transfer_services.request_transfer_exit import RequestTransferExit
        from .services.transfer_services.request_upload import RequestUpload
        from .services.transfer_services.transfer_data import TransferData

        self._factories = {
            int(ServiceID.DIAGNOSTIC_SESSION_CONTROL): DiagnosticSessionControl,
            int(ServiceID.ECU_RESET): ECUReset,
            int(ServiceID.CLEAR_DIAGNOSTIC_INFORMATION): ClearDiagnosticInformation,
            int(ServiceID.READ_DTC_INFORMATION): ReadDTCInformation,
            int(ServiceID.READ_DATA_BY_IDENTIFIER): ReadDataByIdentifier,
            int(ServiceID.READ_MEMORY_BY_ADDRESS): ReadMemoryByAddress,
            int(ServiceID.READ_SCALING_DATA_BY_IDENTIFIER): ReadScalingDataByIdentifier,
            int(ServiceID.SECURITY_ACCESS): SecurityAccess,
            int(ServiceID.COMMUNICATION_CONTROL): CommunicationControl,
            int(ServiceID.AUTHENTICATION): Authentication,
            int(ServiceID.READ_DATA_BY_PERIODIC_IDENTIFIER): ReadDataByPeriodicIdentifier,
            int(ServiceID.DYNAMICALLY_DEFINE_DATA_IDENTIFIER): DynamicallyDefineDataIdentifier,
            int(ServiceID.WRITE_DATA_BY_IDENTIFIER): WriteDataByIdentifier,
            int(ServiceID.INPUT_OUTPUT_CONTROL_BY_IDENTIFIER): InputOutputControlByIdentifier,
            int(ServiceID.ROUTINE_CONTROL): RoutineControl,
            int(ServiceID.REQUEST_DOWNLOAD): RequestDownload,
            int(ServiceID.REQUEST_UPLOAD): RequestUpload,
            int(ServiceID.TRANSFER_DATA): TransferData,
            int(ServiceID.REQUEST_TRANSFER_EXIT): RequestTransferExit,
            int(ServiceID.REQUEST_FILE_TRANSFER): RequestFileTransfer,
            int(ServiceID.WRITE_MEMORY_BY_ADDRESS): WriteMemoryByAddress,
            int(ServiceID.TESTER_PRESENT): TesterPresent,
            int(ServiceID.ACCESS_TIMING_PARAMETER): AccessTimingParameter,
            int(ServiceID.SECURED_DATA_TRANSMISSION): SecuredDataTransmission,
            int(ServiceID.CONTROL_DTC_SETTING): ControlDTCSetting,
            int(ServiceID.RESPONSE_ON_EVENT): ResponseOnEvent,
            int(ServiceID.LINK_CONTROL): LinkControl,
        }

    def register(self, service_id: int, factory: Callable[[UDSClient], IDiagnosticService]) -> None:
        """Register or replace the factory of *service_id* (used by plugins)."""
        with self._lock:
            self._factories[service_id] = factory
            self._services.pop(service_id, None)

    def get(self, service_id: int) -> IDiagnosticService:
        """Return the (cached) service instance for *service_id*.

        Raises:
            ServiceNotSupportedError: No implementation is registered.
        """
        with self._lock:
            if service_id in self._services:
                return self._services[service_id]
            factory = self._factories.get(service_id)
            if factory is None:
                raise ServiceNotSupportedError(
                    f"no implementation registered for service 0x{service_id:02X}"
                )
            service = factory(self.client)
            self._services[service_id] = service
            return service

    # -- execution ------------------------------------------------------------
    def check_preconditions(self, service_id: int) -> None:
        """Verify session and security prerequisites for *service_id*.

        Raises:
            SessionNotSupportedError: The active session forbids the service.
            SecurityAccessDeniedError: The ECU is still locked.
        """
        if not self.validate_preconditions:
            return
        state = self.client.state
        if (
            service_id in NON_DEFAULT_SESSION_SERVICES
            and state.active_session == int(SessionType.DEFAULT)
        ):
            raise SessionNotSupportedError(
                f"service 0x{service_id:02X} requires a non-default session",
                {"active": state.session_label},
            )
        if (
            service_id in SECURITY_REQUIRED_SERVICES
            and state.security_state is not SecurityState.UNLOCKED
        ):
            raise SecurityAccessDeniedError(
                f"service 0x{service_id:02X} requires an unlocked ECU",
                {"security": state.security_state.value},
            )

    def execute(self, service_id: int, *args: Any, **kwargs: Any) -> Any:
        """Execute the service registered for *service_id*."""
        from ..utils.timer_utils import Stopwatch

        service = self.get(service_id)
        record = DispatchRecord(
            service_id=service_id,
            name=type(service).__name__,
            arguments=args,
        )
        watch = Stopwatch().start()
        try:
            self.check_preconditions(service_id)
            result = service.execute(*args, **kwargs)
            return result
        except Exception as exc:  # noqa: BLE001 - recorded and re-raised
            record.succeeded = False
            record.error = str(exc)
            raise
        finally:
            record.duration_ms = watch.stop()
            self.history.append(record)
            del self.history[:-500]

    def send_raw(self, payload: bytes, timeout: float | None = None) -> Any:
        """Send a raw payload, bypassing the service objects."""
        return self.client.send_request(payload, timeout=timeout)

    # -- introspection -----------------------------------------------------------
    def supported_services(self) -> list[int]:
        """Return the sorted list of registered service identifiers."""
        return sorted(self._factories)

    def describe_services(self) -> list[dict[str, Any]]:
        """Return metadata about every registered service for the UI."""
        result: list[dict[str, Any]] = []
        for sid in self.supported_services():
            service = ServiceID.from_byte(sid)
            result.append(
                {
                    "sid": sid,
                    "hex": f"0x{sid:02X}",
                    "name": service.pretty_name if service else f"Service 0x{sid:02X}",
                    "description": service.description if service else "",
                    "requires_security": sid in SECURITY_REQUIRED_SERVICES,
                    "requires_session": sid in NON_DEFAULT_SESSION_SERVICES,
                }
            )
        return result

    def clear_cache(self) -> None:
        """Drop the cached service instances."""
        with self._lock:
            self._services.clear()


__all__ = ["ServiceDispatcher", "DispatchRecord"]
