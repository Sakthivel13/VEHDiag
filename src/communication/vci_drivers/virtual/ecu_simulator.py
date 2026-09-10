"""Configurable UDS ECU simulator.

The simulator answers UDS requests at the payload level. It is attached to a
:class:`VirtualBus` through an ISO-TP handler so that the whole stack -
segmentation, flow control, pending responses - is exercised exactly as with
real hardware.

Configuration is a plain mapping (usually loaded from
``tests/simulation/ecu_simulator_config.yaml``)::

    ecu_simulator:
      supported_sessions: [0x01, 0x02, 0x03]
      security_seed: "A3F20188"
      security_key_algorithm: xor_complement
      dids: {F190: {value: "574241...", name: VIN}}
      dtcs: [{code: "C07300", status: 0x2F, name: Steering angle sensor}]
      response_delay_ms: 5
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from ....core.enums.nrc_enums import NegativeResponseCode as NRC
from ....core.enums.session_enums import SessionType
from ....core.enums.sid_enums import POSITIVE_RESPONSE_OFFSET, SUPPRESS_POS_RSP_BIT, ServiceID
from ....core.models.message_model import BusMessage
from ....utils.byte_utils import hex_to_bytes
from ...isotp_handler import IsoTpConfig, IsoTpHandler
from .virtual_bus import VirtualBus, VirtualBusNode, get_default_bus

_logger = logging.getLogger(__name__)

#: Configuration used when the caller does not provide one.
DEFAULT_SIMULATOR_CONFIG: dict[str, Any] = {
    "name": "Simulated ECU",
    "rx_id": 0x7E0,
    "tx_id": 0x7E8,
    "functional_id": 0x7DF,
    "supported_sessions": [0x01, 0x02, 0x03],
    "security_levels": {
        "0x01": {"seed": "A3F20188", "algorithm": "xor_complement"},
        "0x11": {"seed": "1122334455667788", "algorithm": "add_constant"},
    },
    "max_security_attempts": 3,
    "security_delay_ms": 2000,
    "dids": {
        "F186": {"name": "Active Diagnostic Session", "value": "01"},
        "F187": {"name": "Spare Part Number", "value": "3132333435363738"},
        "F189": {"name": "ECU Software Version", "value": "56312E332E37"},
        "F18C": {"name": "ECU Serial Number", "value": "534E30303132333435"},
        "F190": {
            "name": "VIN",
            "value": "5742415A5A5A30474D3132333435363738",
        },
        "F191": {"name": "ECU Hardware Number", "value": "48573031"},
        # The identification block a flash sequence reads: supplier hardware
        # and software numbers alongside the ECU's own.
        "F192": {"name": "Supplier Hardware Number", "value": "48573031415F52455631"},
        "F193": {"name": "Supplier Hardware Version", "value": "56312E30"},
        "F194": {"name": "Supplier Software Number", "value": "553237394542533656304133"},
        "F195": {"name": "Supplier Software Version", "value": "56302E33612E393033"},
        "F197": {"name": "System Name", "value": "454D532D4F42444949"},
        "F1A0": {"name": "Battery Voltage", "value": "3390"},
    },
    "writable_dids": ["F198", "F199"],
    "dtcs": [
        {"code": "C07300", "status": 0x2F, "name": "Steering angle sensor"},
        {"code": "010000", "status": 0x24, "name": "MAF circuit"},
        {"code": "C10000", "status": 0x09, "name": "Lost communication with ECM"},
    ],
    "routines": {
        "0202": {"name": "Erase memory", "result": "00"},
        "FF00": {"name": "Erase memory (OBD)", "result": "00"},
        "FF01": {"name": "Check programming dependencies", "result": "00"},
    },
    "response_delay_ms": 2,
    "support_pending_response": False,
    "pending_response_count": 1,
    "max_block_length": 0x0402,
    "error_injection": {"enabled": False, "probability": 0.0, "nrc": 0x21},
}


def _algo_xor_complement(seed: bytes, _config: dict[str, Any]) -> bytes:
    """Return ``~seed`` XOR ``0xFF`` per byte - a common demo algorithm."""
    return bytes((~b ^ 0xFF) & 0xFF for b in seed)


def _algo_add_constant(seed: bytes, config: dict[str, Any]) -> bytes:
    """Return each seed byte increased by a constant (default ``0x42``)."""
    constant = int(config.get("constant", 0x42))
    return bytes((b + constant) & 0xFF for b in seed)


def _algo_xor_key(seed: bytes, config: dict[str, Any]) -> bytes:
    """Return the seed XORed with a repeating key."""
    key = hex_to_bytes(str(config.get("key", "FF")))
    if not key:
        key = b"\xff"
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(seed))


#: Seed-key algorithms the simulator understands.
SEED_KEY_ALGORITHMS: dict[str, Callable[[bytes, dict[str, Any]], bytes]] = {
    "xor_complement": _algo_xor_complement,
    "add_constant": _algo_add_constant,
    "xor_key": _algo_xor_key,
}


@dataclass(slots=True)
class SimulatedDTC:
    """One diagnostic trouble code held by the simulator."""

    code: int
    status: int
    name: str = ""
    snapshot: bytes = b""
    extended: bytes = b"\x01"


@dataclass(slots=True)
class SimulatorState:
    """Mutable runtime state of the simulated ECU."""

    session: int = int(SessionType.DEFAULT)
    security_unlocked: int | None = None
    pending_seed: bytes = b""
    pending_level: int = 0
    failed_attempts: int = 0
    delay_until: float = 0.0
    dtc_setting_on: bool = True
    communication_enabled: bool = True
    download_active: bool = False
    block_counter: int = 0
    transferred: bytearray = field(default_factory=bytearray)
    reset_count: int = 0


class ECUSimulator:
    """A UDS server good enough to develop and test the whole application.

    Args:
        config: Simulator configuration; missing keys fall back to
            :data:`DEFAULT_SIMULATOR_CONFIG`.
        bus: Virtual bus to attach to (defaults to the shared bus).

    Example:
        >>> sim = ECUSimulator()
        >>> sim.handle_request(bytes.fromhex("1003")).hex()
        '5003003201f4'
        >>> sim.handle_request(bytes.fromhex("22F186")).hex()
        '62f18603'
    """

    def __init__(self, config: dict[str, Any] | None = None, bus: VirtualBus | None = None) -> None:
        """Load the configuration and prepare the simulated data."""
        merged = dict(DEFAULT_SIMULATOR_CONFIG)
        merged.update(config or {})
        self.config = merged
        self.state = SimulatorState()
        self.bus = bus or get_default_bus()
        self.node: VirtualBusNode | None = None
        self._isotp: IsoTpHandler | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.RLock()

        self.rx_id = int(self.config.get("rx_id", 0x7E0))
        self.tx_id = int(self.config.get("tx_id", 0x7E8))
        self.functional_id = int(self.config.get("functional_id", 0x7DF))
        self.dids: dict[int, bytearray] = {}
        self.did_names: dict[int, str] = {}
        for key, entry in (self.config.get("dids") or {}).items():
            did = int(str(key), 16)
            value = entry.get("value", "") if isinstance(entry, dict) else str(entry)
            self.dids[did] = bytearray(hex_to_bytes(str(value)))
            if isinstance(entry, dict):
                self.did_names[did] = str(entry.get("name", ""))
        self.dtcs: list[SimulatedDTC] = [
            SimulatedDTC(
                code=int(str(item["code"]), 16),
                status=int(item.get("status", 0x08)),
                name=str(item.get("name", "")),
                snapshot=hex_to_bytes(str(item.get("snapshot", "01 02 03 04"))),
                extended=hex_to_bytes(str(item.get("extended", "01"))),
            )
            for item in (self.config.get("dtcs") or [])
        ]
        self.handlers: dict[int, Callable[[bytes], bytes | None]] = {
            ServiceID.DIAGNOSTIC_SESSION_CONTROL: self._svc_session_control,
            ServiceID.ECU_RESET: self._svc_ecu_reset,
            ServiceID.CLEAR_DIAGNOSTIC_INFORMATION: self._svc_clear_dtc,
            ServiceID.READ_DTC_INFORMATION: self._svc_read_dtc,
            ServiceID.READ_DATA_BY_IDENTIFIER: self._svc_read_did,
            ServiceID.SECURITY_ACCESS: self._svc_security_access,
            ServiceID.COMMUNICATION_CONTROL: self._svc_communication_control,
            ServiceID.WRITE_DATA_BY_IDENTIFIER: self._svc_write_did,
            ServiceID.INPUT_OUTPUT_CONTROL_BY_IDENTIFIER: self._svc_io_control,
            ServiceID.ROUTINE_CONTROL: self._svc_routine_control,
            ServiceID.REQUEST_DOWNLOAD: self._svc_request_download,
            ServiceID.TRANSFER_DATA: self._svc_transfer_data,
            ServiceID.REQUEST_TRANSFER_EXIT: self._svc_transfer_exit,
            ServiceID.TESTER_PRESENT: self._svc_tester_present,
            ServiceID.CONTROL_DTC_SETTING: self._svc_control_dtc_setting,
        }

    # -- lifecycle ----------------------------------------------------------
    def start(self) -> None:
        """Attach to the virtual bus and start answering requests."""
        if self._thread is not None and self._thread.is_alive():
            return
        self.node = self.bus.attach(f"ecu-{self.tx_id:X}")
        isotp_config = IsoTpConfig(block_size=8, st_min_ms=0, tx_padding=True)
        self._isotp = IsoTpHandler(self._send_frame, self._next_frame, isotp_config)
        self._stop.clear()
        self._thread = threading.Thread(target=self._serve, name="ecu-sim", daemon=True)
        self._thread.start()
        _logger.info("ECU simulator listening on 0x%X, answering on 0x%X", self.rx_id, self.tx_id)

    def stop(self) -> None:
        """Stop the server thread and detach from the bus."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(1.5)
            self._thread = None
        if self.node is not None:
            self.node.detach()
            self.node = None

    def reset(self) -> None:
        """Return the simulated ECU to its power-on state."""
        with self._lock:
            self.state = SimulatorState()

    # -- bus plumbing --------------------------------------------------------
    def _send_frame(self, data: bytes) -> None:
        """Send one raw frame with the ECU response identifier."""
        if self.node is None:
            return
        self.node.send(BusMessage(data=data, arbitration_id=self.tx_id))

    def _next_frame(self, timeout: float) -> bytes | None:
        """Return the next frame addressed to the simulated ECU."""
        if self.node is None:
            return None
        deadline = time.perf_counter() + max(0.001, timeout)
        while time.perf_counter() < deadline:
            message = self.node.receive(max(0.001, deadline - time.perf_counter()))
            if message is None:
                return None
            if message.arbitration_id in (self.rx_id, self.functional_id):
                return message.data
        return None

    def _serve(self) -> None:
        """Server loop: reassemble a request, answer it, repeat.

        Both the receive and the send side are guarded. A real tester can
        disappear at any moment - for example when the operator disconnects
        the VCI while a multi-frame response is still waiting for a flow
        control frame - and that must never take the simulator down. Any
        transport error simply abandons the current exchange and the loop goes
        back to listening.
        """
        assert self._isotp is not None
        while not self._stop.is_set():
            try:
                request = self._isotp.receive(0.25)
            except Exception:  # noqa: BLE001 - keep the simulator alive
                continue
            if not request:
                continue
            try:
                self._answer(request)
            except Exception:  # noqa: BLE001 - the tester vanished mid-answer
                _logger.debug("simulator abandoned a response", exc_info=True)
                continue

    def _answer(self, request: bytes) -> None:
        """Send the response to *request*, honouring the delay and pending frames.

        Raises:
            Exception: Propagated from the ISO-TP layer when the tester stops
                answering; :meth:`_serve` catches it and keeps serving.
        """
        assert self._isotp is not None
        delay = float(self.config.get("response_delay_ms", 0)) / 1000.0
        if delay:
            time.sleep(delay)
        if self.config.get("support_pending_response"):
            for _ in range(int(self.config.get("pending_response_count", 1))):
                self._isotp.send(
                    bytes(
                        [
                            0x7F,
                            request[0],
                            int(NRC.REQUEST_CORRECTLY_RECEIVED_RESPONSE_PENDING),
                        ]
                    )
                )
                time.sleep(0.01)
        response = self.handle_request(request)
        if response:
            self._isotp.send(response)

    # -- request dispatch -----------------------------------------------------
    def handle_request(self, request: bytes) -> bytes | None:
        """Process one UDS *request* and return the response payload.

        Returns ``None`` when the positive response was suppressed.
        """
        if not request:
            return None
        with self._lock:
            sid = request[0]
            handler = self.handlers.get(sid)
            if handler is None:
                return self._negative(sid, NRC.SERVICE_NOT_SUPPORTED)
            suppress = False
            if len(request) > 1 and self._has_subfunction(sid):
                suppress = bool(request[1] & SUPPRESS_POS_RSP_BIT)
                request = bytes([request[0], request[1] & ~SUPPRESS_POS_RSP_BIT]) + request[2:]
            injected = self._maybe_inject_error(sid)
            if injected is not None:
                return injected
            try:
                response = handler(request)
            except Exception:  # noqa: BLE001 - simulate a general reject
                _logger.exception("simulator handler failed for SID 0x%02X", sid)
                return self._negative(sid, NRC.GENERAL_REJECT)
            if response is None:
                return None
            if suppress and response and response[0] == (sid + POSITIVE_RESPONSE_OFFSET) & 0xFF:
                return None
            return response

    @staticmethod
    def _has_subfunction(sid: int) -> bool:
        """Return ``True`` for services whose second byte is a sub-function."""
        return sid in {
            ServiceID.DIAGNOSTIC_SESSION_CONTROL,
            ServiceID.ECU_RESET,
            ServiceID.READ_DTC_INFORMATION,
            ServiceID.SECURITY_ACCESS,
            ServiceID.COMMUNICATION_CONTROL,
            ServiceID.ROUTINE_CONTROL,
            ServiceID.TESTER_PRESENT,
            ServiceID.CONTROL_DTC_SETTING,
        }

    def _maybe_inject_error(self, sid: int) -> bytes | None:
        """Return an injected negative response when error injection is on."""
        injection = self.config.get("error_injection") or {}
        if not injection.get("enabled"):
            return None
        import random

        if random.random() < float(injection.get("probability", 0.0)):
            return self._negative(sid, int(injection.get("nrc", NRC.BUSY_REPEAT_REQUEST)))
        return None

    @staticmethod
    def _negative(sid: int, nrc: int) -> bytes:
        """Build a negative response payload."""
        return bytes([0x7F, sid & 0xFF, int(nrc) & 0xFF])

    @staticmethod
    def _positive(sid: int, *payload: int | bytes) -> bytes:
        """Build a positive response payload."""
        out = bytearray([(sid + POSITIVE_RESPONSE_OFFSET) & 0xFF])
        for item in payload:
            if isinstance(item, int):
                out.append(item & 0xFF)
            else:
                out.extend(item)
        return bytes(out)

    # -- service implementations -------------------------------------------------
    def _svc_session_control(self, request: bytes) -> bytes:
        """Handle DiagnosticSessionControl (0x10)."""
        if len(request) < 2:
            return self._negative(request[0], NRC.INCORRECT_MESSAGE_LENGTH_OR_INVALID_FORMAT)
        session = request[1]
        supported = [int(s) for s in self.config.get("supported_sessions", [1, 2, 3])]
        if session not in supported:
            return self._negative(request[0], NRC.SUB_FUNCTION_NOT_SUPPORTED)
        self.state.session = session
        if session == int(SessionType.DEFAULT):
            self.state.security_unlocked = None
        # P2 = 50 ms, P2* = 5000 ms (resolution 10 ms -> 0x01F4)
        return self._positive(request[0], session, b"\x00\x32\x01\xf4")

    def _svc_ecu_reset(self, request: bytes) -> bytes:
        """Handle ECUReset (0x11)."""
        if len(request) < 2:
            return self._negative(request[0], NRC.INCORRECT_MESSAGE_LENGTH_OR_INVALID_FORMAT)
        reset_type = request[1]
        if reset_type not in (0x01, 0x02, 0x03):
            return self._negative(request[0], NRC.SUB_FUNCTION_NOT_SUPPORTED)
        self.state = SimulatorState()
        self.state.reset_count += 1
        return self._positive(request[0], reset_type)

    def _svc_read_did(self, request: bytes) -> bytes:
        """Handle ReadDataByIdentifier (0x22), including multi-DID reads."""
        if len(request) < 3 or (len(request) - 1) % 2:
            return self._negative(request[0], NRC.INCORRECT_MESSAGE_LENGTH_OR_INVALID_FORMAT)
        out = bytearray([0x62])
        found = False
        for index in range(1, len(request), 2):
            did = int.from_bytes(request[index : index + 2], "big")
            if did == 0xF186:
                out += request[index : index + 2] + bytes([self.state.session])
                found = True
                continue
            value = self.dids.get(did)
            if value is None:
                continue
            out += request[index : index + 2] + bytes(value)
            found = True
        if not found:
            return self._negative(request[0], NRC.REQUEST_OUT_OF_RANGE)
        return bytes(out)

    def _svc_write_did(self, request: bytes) -> bytes:
        """Handle WriteDataByIdentifier (0x2E)."""
        if len(request) < 4:
            return self._negative(request[0], NRC.INCORRECT_MESSAGE_LENGTH_OR_INVALID_FORMAT)
        if self.state.security_unlocked is None:
            return self._negative(request[0], NRC.SECURITY_ACCESS_DENIED)
        did = int.from_bytes(request[1:3], "big")
        writable = {int(str(d), 16) for d in self.config.get("writable_dids", [])}
        if did not in writable and did not in self.dids:
            return self._negative(request[0], NRC.REQUEST_OUT_OF_RANGE)
        self.dids[did] = bytearray(request[3:])
        return self._positive(request[0], request[1:3])

    def _svc_security_access(self, request: bytes) -> bytes:
        """Handle SecurityAccess (0x27) seed request and key verification."""
        if len(request) < 2:
            return self._negative(request[0], NRC.INCORRECT_MESSAGE_LENGTH_OR_INVALID_FORMAT)
        level = request[1]
        if self.state.session == int(SessionType.DEFAULT):
            return self._negative(request[0], NRC.SERVICE_NOT_SUPPORTED_IN_ACTIVE_SESSION)
        if time.time() < self.state.delay_until:
            return self._negative(request[0], NRC.REQUIRED_TIME_DELAY_NOT_EXPIRED)
        levels = self.config.get("security_levels", {})
        if level % 2 == 1:  # seed request
            entry = levels.get(f"0x{level:02X}") or levels.get(f"0x{level:02x}")
            if entry is None:
                return self._negative(request[0], NRC.SUB_FUNCTION_NOT_SUPPORTED)
            seed = hex_to_bytes(str(entry.get("seed", "00000000")))
            if self.state.security_unlocked == level + 1:
                seed = bytes(len(seed))  # already unlocked -> zero seed
            self.state.pending_seed = seed
            self.state.pending_level = level
            return self._positive(request[0], level, seed)
        # key verification
        seed_level = level - 1
        entry = levels.get(f"0x{seed_level:02X}") or levels.get(f"0x{seed_level:02x}")
        if entry is None or self.state.pending_level != seed_level:
            return self._negative(request[0], NRC.REQUEST_SEQUENCE_ERROR)
        algorithm = SEED_KEY_ALGORITHMS.get(str(entry.get("algorithm", "xor_complement")))
        expected = algorithm(self.state.pending_seed, entry) if algorithm else b""
        if bytes(request[2:]) != expected:
            self.state.failed_attempts += 1
            if self.state.failed_attempts >= int(self.config.get("max_security_attempts", 3)):
                self.state.delay_until = time.time() + float(
                    self.config.get("security_delay_ms", 2000)
                ) / 1000.0
                self.state.failed_attempts = 0
                return self._negative(request[0], NRC.EXCEEDED_NUMBER_OF_ATTEMPTS)
            return self._negative(request[0], NRC.INVALID_KEY)
        self.state.failed_attempts = 0
        self.state.security_unlocked = level
        self.state.pending_seed = b""
        return self._positive(request[0], level)

    def _svc_read_dtc(self, request: bytes) -> bytes:
        """Handle ReadDTCInformation (0x19) for the common sub-functions."""
        if len(request) < 2:
            return self._negative(request[0], NRC.INCORRECT_MESSAGE_LENGTH_OR_INVALID_FORMAT)
        sub = request[1]
        availability = 0xFF
        if sub == 0x01:  # reportNumberOfDTCByStatusMask
            mask = request[2] if len(request) > 2 else 0xFF
            count = sum(1 for d in self.dtcs if d.status & mask)
            return self._positive(request[0], sub, availability, 0x01, count >> 8, count & 0xFF)
        if sub in (0x02, 0x0A, 0x15):  # by status mask / supported / permanent
            mask = request[2] if len(request) > 2 and sub == 0x02 else 0xFF
            out = bytearray([0x59, sub, availability])
            for dtc in self.dtcs:
                if dtc.status & mask:
                    out += dtc.code.to_bytes(3, "big") + bytes([dtc.status])
            return bytes(out)
        if sub == 0x04:  # snapshot by DTC number
            if len(request) < 5:
                return self._negative(request[0], NRC.INCORRECT_MESSAGE_LENGTH_OR_INVALID_FORMAT)
            code = int.from_bytes(request[2:5], "big")
            record = request[5] if len(request) > 5 else 0x01
            for dtc in self.dtcs:
                if dtc.code == code:
                    return bytes(
                        bytearray([0x59, sub])
                        + dtc.code.to_bytes(3, "big")
                        + bytes([dtc.status, record, 0x01])
                        + dtc.snapshot
                    )
            return self._negative(request[0], NRC.REQUEST_OUT_OF_RANGE)
        if sub == 0x06:  # extended data by DTC number
            if len(request) < 5:
                return self._negative(request[0], NRC.INCORRECT_MESSAGE_LENGTH_OR_INVALID_FORMAT)
            code = int.from_bytes(request[2:5], "big")
            record = request[5] if len(request) > 5 else 0x01
            for dtc in self.dtcs:
                if dtc.code == code:
                    return bytes(
                        bytearray([0x59, sub])
                        + dtc.code.to_bytes(3, "big")
                        + bytes([dtc.status, record])
                        + dtc.extended
                    )
            return self._negative(request[0], NRC.REQUEST_OUT_OF_RANGE)
        return self._negative(request[0], NRC.SUB_FUNCTION_NOT_SUPPORTED)

    def _svc_clear_dtc(self, request: bytes) -> bytes:
        """Handle ClearDiagnosticInformation (0x14)."""
        if len(request) < 4:
            return self._negative(request[0], NRC.INCORRECT_MESSAGE_LENGTH_OR_INVALID_FORMAT)
        group = int.from_bytes(request[1:4], "big")
        if group == 0xFFFFFF:
            self.dtcs.clear()
        else:
            low, high = group, group | 0x00FFFF
            self.dtcs = [d for d in self.dtcs if not low <= d.code <= high]
        return self._positive(request[0])

    def _svc_control_dtc_setting(self, request: bytes) -> bytes:
        """Handle ControlDTCSetting (0x85)."""
        if len(request) < 2 or request[1] not in (0x01, 0x02):
            return self._negative(request[0], NRC.SUB_FUNCTION_NOT_SUPPORTED)
        self.state.dtc_setting_on = request[1] == 0x01
        return self._positive(request[0], request[1])

    def _svc_communication_control(self, request: bytes) -> bytes:
        """Handle CommunicationControl (0x28)."""
        if len(request) < 3:
            return self._negative(request[0], NRC.INCORRECT_MESSAGE_LENGTH_OR_INVALID_FORMAT)
        self.state.communication_enabled = request[1] == 0x00
        return self._positive(request[0], request[1])

    def _svc_io_control(self, request: bytes) -> bytes:
        """Handle InputOutputControlByIdentifier (0x2F)."""
        if len(request) < 4:
            return self._negative(request[0], NRC.INCORRECT_MESSAGE_LENGTH_OR_INVALID_FORMAT)
        if self.state.session == int(SessionType.DEFAULT):
            return self._negative(request[0], NRC.SERVICE_NOT_SUPPORTED_IN_ACTIVE_SESSION)
        return self._positive(request[0], request[1:4])

    def _svc_routine_control(self, request: bytes) -> bytes:
        """Handle RoutineControl (0x31)."""
        if len(request) < 4:
            return self._negative(request[0], NRC.INCORRECT_MESSAGE_LENGTH_OR_INVALID_FORMAT)
        sub, routine = request[1], request[2:4]
        if sub not in (0x01, 0x02, 0x03):
            return self._negative(request[0], NRC.SUB_FUNCTION_NOT_SUPPORTED)
        routines = self.config.get("routines", {})
        entry = routines.get(routine.hex().upper()) or {}
        result = hex_to_bytes(str(entry.get("result", "00")))
        return self._positive(request[0], sub, routine, result)

    def _svc_request_download(self, request: bytes) -> bytes:
        """Handle RequestDownload (0x34)."""
        if self.state.session != int(SessionType.PROGRAMMING):
            return self._negative(request[0], NRC.SERVICE_NOT_SUPPORTED_IN_ACTIVE_SESSION)
        if self.state.security_unlocked is None:
            return self._negative(request[0], NRC.SECURITY_ACCESS_DENIED)
        self.state.download_active = True
        self.state.block_counter = 0
        self.state.transferred = bytearray()
        max_block = int(self.config.get("max_block_length", 0x0402))
        return self._positive(request[0], 0x20, max_block >> 8, max_block & 0xFF)

    def _svc_transfer_data(self, request: bytes) -> bytes:
        """Handle TransferData (0x36) with block sequence counter checks."""
        if not self.state.download_active:
            return self._negative(request[0], NRC.REQUEST_SEQUENCE_ERROR)
        if len(request) < 2:
            return self._negative(request[0], NRC.INCORRECT_MESSAGE_LENGTH_OR_INVALID_FORMAT)
        expected = (self.state.block_counter + 1) & 0xFF
        if request[1] != expected:
            return self._negative(request[0], NRC.WRONG_BLOCK_SEQUENCE_COUNTER)
        self.state.block_counter = expected
        self.state.transferred.extend(request[2:])
        return self._positive(request[0], expected)

    def _svc_transfer_exit(self, request: bytes) -> bytes:
        """Handle RequestTransferExit (0x37)."""
        if not self.state.download_active:
            return self._negative(request[0], NRC.REQUEST_SEQUENCE_ERROR)
        self.state.download_active = False
        size = len(self.state.transferred)
        return self._positive(request[0], size >> 8 & 0xFF, size & 0xFF)

    def _svc_tester_present(self, request: bytes) -> bytes:
        """Handle TesterPresent (0x3E)."""
        sub = request[1] if len(request) > 1 else 0x00
        return self._positive(request[0], sub)

    # -- introspection ---------------------------------------------------------------
    def snapshot(self) -> dict[str, Any]:
        """Return a mapping describing the simulator state (used in tests)."""
        return {
            "session": self.state.session,
            "security_unlocked": self.state.security_unlocked,
            "dtc_count": len(self.dtcs),
            "download_active": self.state.download_active,
            "transferred_bytes": len(self.state.transferred),
            "reset_count": self.state.reset_count,
        }

    def __repr__(self) -> str:  # noqa: D105 - trivial
        return f"<ECUSimulator rx=0x{self.rx_id:X} tx=0x{self.tx_id:X} session=0x{self.state.session:02X}>"


__all__ = ["ECUSimulator", "SimulatedDTC", "SimulatorState", "DEFAULT_SIMULATOR_CONFIG", "SEED_KEY_ALGORITHMS"]
