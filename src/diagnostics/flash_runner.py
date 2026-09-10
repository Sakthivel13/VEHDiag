"""Execute a :class:`~src.diagnostics.flash_sequence.FlashSequence`.

The runner walks the steps in the order the operator arranged them, reports
progress through callbacks and stops at the first failure unless told
otherwise. It owns no Qt objects, so the whole flash can be replayed in a unit
test against the built-in ECU simulator.

Example:
    >>> from src.diagnostics.flash_sequence import FlashSequence, FlashStepKind
    >>> runner = FlashRunner(client=None)
    >>> runner.sequence = FlashSequence(steps=[])
    >>> runner.run().completed
    True
"""
from __future__ import annotations

import binascii
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ..core.enums.session_enums import SessionType
from ..core.models.file_transfer_model import MemorySegment, TransferProgress
from .flash_sequence import (
    FlashSequence,
    FlashStep,
    FlashStepKind,
    StepOutcome,
    StepStatus,
)

_logger = logging.getLogger(__name__)

__all__ = ["FlashReport", "FlashRunner"]

#: Routine identifiers used by the default sequence.
ERASE_ROUTINE = 0xFF00
CHECK_DEPENDENCIES_ROUTINE = 0xFF01
CHECK_MEMORY_ROUTINE = 0x0202

#: Identification DIDs read by the read steps.
DID_VIN = 0xF190
DID_HARDWARE = (0xF191, 0xF192)
DID_SOFTWARE = (0xF194, 0xF195)
DID_BATTERY = 0xF1A0


@dataclass(slots=True)
class FlashReport:
    """Outcome of a whole sequence run.

    Attributes:
        outcomes: One entry per executed step.
        started_at: Wall clock start time.
        duration_s: Total run time.
        cancelled: The operator aborted the run.
        info: Values collected on the way, e.g. the VIN and the CRC.
    """

    outcomes: list[StepOutcome] = field(default_factory=list)
    started_at: float = 0.0
    duration_s: float = 0.0
    cancelled: bool = False
    info: dict[str, Any] = field(default_factory=dict)

    @property
    def failed(self) -> list[StepOutcome]:
        """Return the steps that failed."""
        return [o for o in self.outcomes if o.status is StepStatus.FAILED]

    @property
    def completed(self) -> bool:
        """Return ``True`` when nothing failed and the run was not cancelled."""
        return not self.failed and not self.cancelled

    def summary(self) -> str:
        """Return the one line summary shown when the run ends.

        Example:
            >>> FlashReport().summary()
            'nothing executed'
        """
        if not self.outcomes:
            return "nothing executed"
        passed = sum(1 for o in self.outcomes if o.status is StepStatus.PASSED)
        skipped = sum(1 for o in self.outcomes if o.status is StepStatus.SKIPPED)
        parts = [f"{passed} passed"]
        if self.failed:
            parts.append(f"{len(self.failed)} failed")
        if skipped:
            parts.append(f"{skipped} skipped")
        if self.cancelled:
            parts.append("cancelled")
        return ", ".join(parts) + f" in {self.duration_s:.1f} s"


class FlashRunner:
    """Runs a flash sequence step by step.

    Args:
        client: The :class:`~src.diagnostics.uds_client.UDSClient` to drive.
        connection: Optional connection manager, used by the CAN steps.
        on_step: Called with the :class:`FlashStep` when a step starts.
        on_step_done: Called with the :class:`StepOutcome` when it finishes.
        on_progress: Called with a :class:`TransferProgress` during the
            transfer step.
        on_log: Called with every human readable log line.

    Attributes:
        sequence: The sequence being executed.
        segments: The memory segments staged by the file upload step.
    """

    def __init__(
        self,
        client: Any,
        connection: Any = None,
        on_step: Callable[[FlashStep], None] | None = None,
        on_step_done: Callable[[StepOutcome], None] | None = None,
        on_progress: Callable[[TransferProgress], None] | None = None,
        on_log: Callable[[str], None] | None = None,
    ) -> None:
        """Store the client and the callbacks."""
        self.client = client
        self.connection = connection
        self.on_step = on_step
        self.on_step_done = on_step_done
        self.on_progress = on_progress
        self.on_log = on_log
        self.sequence = FlashSequence.default()
        self.segments: list[MemorySegment] = []
        self.report = FlashReport()
        self._cancelled = False
        self._block_size = 0

    # -- control -------------------------------------------------------------
    def cancel(self) -> None:
        """Ask the run to stop at the next opportunity."""
        self._cancelled = True
        self._log("cancellation requested")

    @property
    def cancelled(self) -> bool:
        """Return ``True`` when a cancellation is pending."""
        return self._cancelled

    def _log(self, message: str) -> None:
        """Publish *message* to the log callback and the logger."""
        _logger.info("flash: %s", message)
        if self.on_log is not None:
            self.on_log(message)

    # -- execution -----------------------------------------------------------
    def run(self, sequence: FlashSequence | None = None, stop_on_failure: bool = True) -> FlashReport:
        """Execute *sequence* and return the report.

        Args:
            sequence: The sequence to run; the stored one when omitted.
            stop_on_failure: Abort at the first failing step.

        Returns:
            The :class:`FlashReport` describing the run.
        """
        if sequence is not None:
            self.sequence = sequence
        self._cancelled = False
        self.segments = []
        self.sequence.reset()
        self.report = FlashReport(started_at=time.time())
        started = time.perf_counter()

        self._log(f"starting '{self.sequence.name}' with {len(self.sequence.enabled_steps)} step(s)")
        for step in self.sequence.steps:
            if self._cancelled:
                self.report.cancelled = True
                step.status = StepStatus.SKIPPED
                break
            if not step.enabled:
                step.status = StepStatus.SKIPPED
                outcome = StepOutcome(step, StepStatus.SKIPPED, "disabled")
                self.report.outcomes.append(outcome)
                continue
            outcome = self._run_step(step)
            self.report.outcomes.append(outcome)
            if outcome.status is StepStatus.FAILED and stop_on_failure:
                self._log(f"aborting: {step.label} failed - {outcome.message}")
                break

        self.report.duration_s = time.perf_counter() - started
        self._log(self.report.summary())
        return self.report

    def _run_step(self, step: FlashStep) -> StepOutcome:
        """Execute one step, timing it and capturing any failure."""
        step.status = StepStatus.RUNNING
        step.message = ""
        if self.on_step is not None:
            self.on_step(step)
        self._log(f"-> {step.label}")
        started = time.perf_counter()
        try:
            handler = self._handlers().get(step.kind)
            if handler is None:
                raise NotImplementedError(f"no handler for {step.kind.value}")
            data = handler(step) or {}
            status, message = StepStatus.PASSED, str(data.pop("message", "ok"))
        except Exception as exc:  # noqa: BLE001 - every failure is reported
            status, message, data = StepStatus.FAILED, f"{type(exc).__name__}: {exc}", {}
            _logger.debug("step %s failed", step.kind.value, exc_info=True)
        duration = (time.perf_counter() - started) * 1000.0
        step.status = status
        step.message = message
        step.duration_ms = duration
        self.report.info.update(data)
        outcome = StepOutcome(step, status, message, duration, data)
        self._log(f"   {status.value}: {message} ({duration:.0f} ms)")
        if self.on_step_done is not None:
            self.on_step_done(outcome)
        return outcome

    def _handlers(self) -> dict[FlashStepKind, Callable[[FlashStep], dict[str, Any] | None]]:
        """Return the handler for every supported step kind."""
        K = FlashStepKind
        return {
            K.CAN_INIT: self._can_init,
            K.CAN_CONFIG: self._can_config,
            K.ECU_COMM: self._ecu_comm,
            K.READ_VIN: self._read_vin,
            K.READ_HARDWARE: self._read_hardware,
            K.READ_SOFTWARE: self._read_software,
            K.SECURITY_ACCESS: self._security_access,
            K.ERASE_MEMORY: self._erase_memory,
            K.FILE_UPLOAD: self._file_upload,
            K.REQUEST_DOWNLOAD: self._request_download,
            K.TRANSFER_DATA: self._transfer_data,
            K.TRANSFER_EXIT: self._transfer_exit,
            K.ECU_RESET: self._ecu_reset,
            K.ENTER_EXTENDED: lambda s: self._change_session(0x03),
            K.ENTER_PROGRAMMING: lambda s: self._change_session(0x02),
            K.ENTER_DEFAULT: lambda s: self._change_session(0x01),
            K.TESTER_PRESENT: self._tester_present,
            K.DISABLE_DTC: lambda s: self._dtc_setting(False),
            K.ENABLE_DTC: lambda s: self._dtc_setting(True),
            K.DISABLE_COMMUNICATION: lambda s: self._communication(0x03),
            K.ENABLE_COMMUNICATION: lambda s: self._communication(0x00),
            K.CLEAR_DTC: self._clear_dtc,
            K.READ_DTC: self._read_dtc,
            K.CHECK_PROGRAMMING_DEPENDENCIES: self._check_dependencies,
            K.CHECK_MEMORY: self._check_memory,
            K.VERIFY_CHECKSUM: self._verify_checksum,
            K.READ_BATTERY_VOLTAGE: self._read_battery,
            K.READ_DID: self._read_did,
            K.WRITE_DID: self._write_did,
            K.ROUTINE_CONTROL: self._routine_control,
            K.RAW_REQUEST: self._raw_request,
            K.DELAY: self._delay,
        }

    # -- connection steps ----------------------------------------------------
    def _can_init(self, step: FlashStep) -> dict[str, Any]:
        """Open the VCI channel."""
        if self.connection is None:
            return {"message": "already connected (no connection manager)"}
        if getattr(self.connection, "is_connected", False):
            return {"message": "channel already open"}
        self.connection.connect()
        return {"message": "channel opened"}

    def _can_config(self, step: FlashStep) -> dict[str, Any]:
        """Report the applied bitrate and identifiers."""
        info = self.connection.get_info() if self.connection is not None else {}
        profile = info.get("profile", {}) if isinstance(info, dict) else {}
        if profile:
            return {
                "message": (
                    f"{profile.get('protocol', 'CAN')} @ {profile.get('bitrate', '?')} bit/s, "
                    f"TX 0x{int(profile.get('tx_id', 0)):X} RX 0x{int(profile.get('rx_id', 0)):X}"
                )
            }
        return {"message": "using the current transport configuration"}

    def _ecu_comm(self, step: FlashStep) -> dict[str, Any]:
        """Confirm the ECU answers."""
        response = self.client.tester_present(suppress=False)
        if not response.is_positive():
            raise RuntimeError(f"no positive response: {response.nrc_text}")
        return {"message": "ECU responded to tester present"}

    # -- identification steps ------------------------------------------------
    def _read_did_value(self, did: int) -> bytes:
        """Return the payload of *did*, raising when the read fails."""
        response = self.client.read_data_by_identifier(did)
        if not response.is_positive():
            raise RuntimeError(f"DID 0x{did:04X}: {response.nrc_text}")
        return bytes(response.data[2:])

    def _read_vin(self, step: FlashStep) -> dict[str, Any]:
        """Read DID 0xF190."""
        vin = self._read_did_value(DID_VIN).decode("ascii", errors="replace").strip("\x00")
        return {"vin": vin, "message": f"VIN {vin}"}

    def _read_hardware(self, step: FlashStep) -> dict[str, Any]:
        """Read the hardware identification DIDs."""
        values = []
        for did in DID_HARDWARE:
            try:
                values.append(
                    self._read_did_value(did).decode("ascii", errors="replace").strip("\x00")
                )
            except Exception:  # noqa: BLE001 - an optional DID may be absent
                continue
        if not values:
            raise RuntimeError("no hardware identification DID answered")
        return {"hardware": values, "message": " / ".join(values)}

    def _read_software(self, step: FlashStep) -> dict[str, Any]:
        """Read the software identification DIDs."""
        values = []
        for did in DID_SOFTWARE:
            try:
                values.append(
                    self._read_did_value(did).decode("ascii", errors="replace").strip("\x00")
                )
            except Exception:  # noqa: BLE001 - an optional DID may be absent
                continue
        if not values:
            raise RuntimeError("no software identification DID answered")
        return {"software": values, "message": " / ".join(values)}

    def _read_battery(self, step: FlashStep) -> dict[str, Any]:
        """Read the supply voltage and warn when it is too low to flash."""
        raw = self._read_did_value(int(step.options.get("did", DID_BATTERY)))
        millivolts = int.from_bytes(raw[:2], "big") if len(raw) >= 2 else 0
        volts = millivolts / 1000.0
        minimum = float(step.options.get("minimum_v", 11.0))
        if volts and volts < minimum:
            raise RuntimeError(f"supply voltage {volts:.2f} V is below {minimum:.1f} V")
        return {"battery_v": volts, "message": f"{volts:.2f} V" if volts else "unavailable"}

    # -- session steps -------------------------------------------------------
    def _change_session(self, session: int) -> dict[str, Any]:
        """Switch the diagnostic session."""
        response = self.client.change_session(session)
        if not response.is_positive():
            raise RuntimeError(f"session 0x{session:02X}: {response.nrc_text}")
        return {"message": f"session 0x{session:02X} active"}

    def _tester_present(self, step: FlashStep) -> dict[str, Any]:
        """Send a tester present."""
        self.client.tester_present()
        return {"message": "keep-alive sent"}

    def _security_access(self, step: FlashStep) -> dict[str, Any]:
        """Request the seed and send the computed key."""
        from .services.security.security_access import SecurityAccess

        level = int(step.options.get("level", self.sequence.security_level))
        algorithm = str(step.options.get("algorithm", self.sequence.security_algorithm))
        service = SecurityAccess(self.client, algorithm)
        if self.sequence.security_file is not None:
            service = self._load_security_file(service)
        result = service.execute(level)
        if not result.unlocked:
            raise RuntimeError(f"level 0x{level:02X} refused")
        return {"security_level": level, "message": f"level 0x{level:02X} unlocked"}

    def _load_security_file(self, service: Any) -> Any:
        """Attach the operator supplied seed-key implementation to *service*."""
        from .services.security.security_dll_loader import SecurityDLLLoader

        path = Path(self.sequence.security_file or "")
        loader = SecurityDLLLoader()
        loaded = (
            loader.load_script(path)
            if path.suffix.lower() == ".py"
            else loader.load_library(path)
        )
        service.algorithm = loaded
        self._log(f"   seed-key from {path.name}")
        return service

    # -- precondition steps --------------------------------------------------
    def _dtc_setting(self, on: bool) -> dict[str, Any]:
        """Enable or disable DTC storage."""
        response = self.client.control_dtc_setting(on)
        if not response.is_positive():
            raise RuntimeError(response.nrc_text)
        return {"message": "DTC storage " + ("on" if on else "off")}

    def _communication(self, control_type: int) -> dict[str, Any]:
        """Enable or disable normal communication."""
        response = self.client.communication_control(control_type)
        if not response.is_positive():
            raise RuntimeError(response.nrc_text)
        return {"message": f"communication control 0x{control_type:02X}"}

    def _clear_dtc(self, step: FlashStep) -> dict[str, Any]:
        """Clear the fault memory."""
        group = int(step.options.get("group", 0xFFFFFF))
        response = self.client.clear_diagnostic_information(group)
        if not response.is_positive():
            raise RuntimeError(response.nrc_text)
        return {"message": f"group 0x{group:06X} cleared"}

    def _read_dtc(self, step: FlashStep) -> dict[str, Any]:
        """Read the fault memory."""
        from .services.dtc_services.dtc_parser import parse_dtc_list

        mask = int(step.options.get("status_mask", 0xFF))
        response = self.client.read_dtc_information(0x02, mask)
        if not response.is_positive():
            raise RuntimeError(response.nrc_text)
        dtcs = parse_dtc_list(bytes(response.data[2:]))
        return {"dtc_count": len(dtcs), "message": f"{len(dtcs)} DTC(s)"}

    def _routine(self, routine_id: int, sub_function: int = 0x01, data: bytes = b"") -> None:
        """Start a routine and raise when the ECU refuses."""
        response = self.client.routine_control(sub_function, routine_id, data)
        if not response.is_positive():
            raise RuntimeError(f"routine 0x{routine_id:04X}: {response.nrc_text}")

    def _check_dependencies(self, step: FlashStep) -> dict[str, Any]:
        """Run the programming dependency check routine."""
        routine = int(step.options.get("routine_id", CHECK_DEPENDENCIES_ROUTINE))
        self._routine(routine)
        return {"message": f"routine 0x{routine:04X} accepted"}

    def _check_memory(self, step: FlashStep) -> dict[str, Any]:
        """Run the memory check routine."""
        routine = int(step.options.get("routine_id", CHECK_MEMORY_ROUTINE))
        self._routine(routine)
        return {"message": f"routine 0x{routine:04X} accepted"}

    def _erase_memory(self, step: FlashStep) -> dict[str, Any]:
        """Run the erase routine over the target address range."""
        routine = int(step.options.get("routine_id", ERASE_ROUTINE))
        address = self._target_address()
        size = self._payload_size()
        payload = b""
        if address is not None and size:
            payload = address.to_bytes(4, "big") + size.to_bytes(4, "big")
        self._routine(routine, 0x01, payload)
        span = f" 0x{address:08X}+{size}" if payload else ""
        return {"message": f"erase routine 0x{routine:04X} accepted{span}"}

    # -- transfer steps ------------------------------------------------------
    def _file_upload(self, step: FlashStep) -> dict[str, Any]:
        """Parse the flash file into memory segments."""
        from ..data_processing.file_parsers import parse_firmware_file

        path = step.options.get("path") or self.sequence.flash_file
        if not path:
            raise RuntimeError("no flash file selected")
        resolved = Path(path)
        if not resolved.is_file():
            raise RuntimeError(f"{resolved} does not exist")
        options: dict[str, Any] = {}
        if self.sequence.base_address is not None:
            options["base_address"] = self.sequence.base_address
        self.segments = list(parse_firmware_file(resolved, **options))
        if not self.segments:
            raise RuntimeError("the file contains no data")
        total = sum(segment.size for segment in self.segments)
        return {
            "file": resolved.name,
            "segments": len(self.segments),
            "bytes": total,
            "message": (
                f"{resolved.name}: {len(self.segments)} segment(s), {total} bytes "
                f"from 0x{self.segments[0].address:08X}"
            ),
        }

    def _payload(self) -> bytes:
        """Return the contiguous payload staged by the upload step."""
        if not self.segments:
            raise RuntimeError("run the file upload step first")
        return b"".join(segment.data for segment in self.segments)

    def _payload_size(self) -> int:
        """Return the number of bytes to transfer."""
        return sum(segment.size for segment in self.segments)

    def _target_address(self) -> int | None:
        """Return the download address."""
        if self.sequence.base_address is not None:
            return self.sequence.base_address
        return self.segments[0].address if self.segments else None

    def _request_download(self, step: FlashStep) -> dict[str, Any]:
        """Negotiate the block size with the ECU."""
        from .services.transfer_services.request_download import RequestDownload

        address = self._target_address()
        if address is None:
            raise RuntimeError("no target address; run the file upload step first")
        size = self._payload_size()
        permission = RequestDownload(self.client).execute(address, size)
        self._block_size = int(getattr(permission, "max_block_length", 0) or 0)
        if self.sequence.block_size:
            self._block_size = min(self._block_size or self.sequence.block_size,
                                   self.sequence.block_size)
        return {
            "block_size": self._block_size,
            "message": (
                f"0x{address:08X}, {size} bytes, block size {self._block_size or 'ECU default'}"
            ),
        }

    def _transfer_data(self, step: FlashStep) -> dict[str, Any]:
        """Send the blocks, reporting progress as they go."""
        from .services.transfer_services.transfer_manager import (
            TransferManager,
            TransferOptions,
        )

        payload = self._payload()
        address = self._target_address() or 0
        block_size = int(step.options.get("block_size", 0)) or self._block_size
        manager = TransferManager(self.client, on_progress=self._forward_progress)
        options = TransferOptions(block_size=block_size, verify_after_transfer=True)
        report = manager.download(address, payload, options)
        if report.state.value != "COMPLETED":
            raise RuntimeError(report.message or "transfer did not complete")
        self.report.info["crc32"] = report.crc32
        return {
            "bytes": report.bytes_transferred,
            "blocks": report.blocks,
            "crc32": report.crc32,
            "message": (
                f"{report.bytes_transferred} bytes in {report.blocks} block(s), "
                f"CRC32 0x{report.crc32:08X}"
                if report.crc32 is not None
                else f"{report.bytes_transferred} bytes in {report.blocks} block(s)"
            ),
        }

    def _forward_progress(self, progress: TransferProgress) -> None:
        """Relay a transfer progress update to the UI callback."""
        if self.on_progress is not None:
            self.on_progress(progress)

    def _transfer_exit(self, step: FlashStep) -> dict[str, Any]:
        """Close the transfer.

        ``TransferManager.download`` already sends ``RequestTransferExit``, so
        this step is a no-op when it follows the transfer directly; it exists
        as its own step because some bootloaders want it sent separately.
        """
        from .services.transfer_services.request_transfer_exit import RequestTransferExit

        try:
            RequestTransferExit(self.client).execute()
            return {"message": "transfer closed"}
        except Exception as exc:  # noqa: BLE001 - already closed is not fatal
            return {"message": f"already closed by the transfer step ({exc})"}

    def _verify_checksum(self, step: FlashStep) -> dict[str, Any]:
        """Compare the CRC of the payload with the expected value."""
        payload = self._payload()
        crc = binascii.crc32(payload) & 0xFFFFFFFF
        reported = self.report.info.get("crc32")
        if reported is not None and reported != crc:
            raise RuntimeError(
                f"checksum mismatch: transferred 0x{reported:08X}, file 0x{crc:08X}"
            )
        return {"crc32": crc, "message": f"CRC32 0x{crc:08X} verified"}

    # -- finalisation --------------------------------------------------------
    def _ecu_reset(self, step: FlashStep) -> dict[str, Any]:
        """Reset the ECU."""
        reset_type = int(step.options.get("reset_type", 0x01))
        response = self.client.ecu_reset(reset_type)
        if not response.is_positive():
            raise RuntimeError(response.nrc_text)
        return {"message": f"reset type 0x{reset_type:02X} accepted"}

    # -- generic steps -------------------------------------------------------
    def _read_did(self, step: FlashStep) -> dict[str, Any]:
        """Read an arbitrary data identifier."""
        did = int(step.options.get("did", DID_VIN))
        raw = self._read_did_value(did)
        return {"message": f"DID 0x{did:04X} = {raw.hex().upper()}"}

    def _write_did(self, step: FlashStep) -> dict[str, Any]:
        """Write an arbitrary data identifier."""
        did = int(step.options.get("did", 0))
        data = step.options.get("data", b"")
        payload = bytes.fromhex(data) if isinstance(data, str) else bytes(data)
        response = self.client.write_data_by_identifier(did, payload)
        if not response.is_positive():
            raise RuntimeError(response.nrc_text)
        return {"message": f"DID 0x{did:04X} written"}

    def _routine_control(self, step: FlashStep) -> dict[str, Any]:
        """Run an arbitrary routine."""
        routine = int(step.options.get("routine_id", 0x0203))
        sub = int(step.options.get("sub_function", 0x01))
        data = step.options.get("data", b"")
        payload = bytes.fromhex(data) if isinstance(data, str) else bytes(data)
        self._routine(routine, sub, payload)
        return {"message": f"routine 0x{routine:04X} sub 0x{sub:02X} accepted"}

    def _raw_request(self, step: FlashStep) -> dict[str, Any]:
        """Send arbitrary request bytes."""
        data = step.options.get("data", b"")
        payload = bytes.fromhex(data) if isinstance(data, str) else bytes(data)
        if not payload:
            raise RuntimeError("no request bytes configured")
        response = self.client.send_request(payload)
        return {"message": f"{payload.hex().upper()} -> {response.raw.hex().upper() or '(none)'}"}

    def _delay(self, step: FlashStep) -> dict[str, Any]:
        """Wait for a configured number of milliseconds."""
        milliseconds = int(step.options.get("milliseconds", 500))
        deadline = time.perf_counter() + milliseconds / 1000.0
        while time.perf_counter() < deadline and not self._cancelled:
            time.sleep(0.01)
        return {"message": f"waited {milliseconds} ms"}
