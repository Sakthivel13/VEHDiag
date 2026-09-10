"""Unit tests for the individual UDS services."""
from __future__ import annotations

import pytest

from src.core.enums.session_enums import SessionType
from src.diagnostics.services.data_services.read_data_by_id import (
    ReadDataByIdentifier,
    build_registry,
)
from src.diagnostics.services.dtc_services.clear_dtc import ClearDiagnosticInformation
from src.diagnostics.services.dtc_services.dtc_parser import (
    format_dtc,
    from_sae_code,
    parse_dtc_list,
    to_sae_code,
)
from src.diagnostics.services.dtc_services.dtc_status_mask import StatusMask
from src.diagnostics.services.dtc_services.read_dtc_information import ReadDTCInformation
from src.diagnostics.services.ecu_reset.ecu_reset_service import ECUReset
from src.diagnostics.services.io_control.io_control_by_id import InputOutputControlByIdentifier
from src.diagnostics.services.routine_control.routine_control import RoutineControl
from src.diagnostics.services.security.security_access import SecurityAccess
from src.diagnostics.services.security.security_algorithms import compute_key
from src.diagnostics.services.session_control.diagnostic_session_control import (
    DiagnosticSessionControl,
)
from src.diagnostics.services.transfer_services.block_sequence_counter import BlockSequenceCounter
from src.diagnostics.services.transfer_services.transfer_manager import TransferManager
from src.core.exceptions import TransferError


class TestSessionControl:
    """DiagnosticSessionControl (0x10)."""

    def test_enter_extended(self, client) -> None:
        """The extended session is accepted."""
        result = DiagnosticSessionControl(client).enter_extended()
        assert result.accepted
        assert result.session == int(SessionType.EXTENDED_DIAGNOSTIC)
        assert result.timing.p2_server_ms == 50.0

    def test_enter_default(self, client) -> None:
        """Returning to the default session works."""
        service = DiagnosticSessionControl(client)
        service.enter_extended()
        assert service.enter_default().session == int(SessionType.DEFAULT)

    def test_invalid_sub_function(self, client) -> None:
        """A sub-function outside the range is refused locally."""
        from src.core.exceptions import RequestValidationError

        with pytest.raises(RequestValidationError):
            DiagnosticSessionControl(client).build_request(0xFF)

    def test_client_timing_is_updated(self, client) -> None:
        """The client adopts the timing reported by the ECU."""
        DiagnosticSessionControl(client).enter_extended()
        assert client.config.p2_client_ms >= 50.0


class TestReadDataByIdentifier:
    """ReadDataByIdentifier (0x22)."""

    def test_read_vin(self, client, config) -> None:
        """The VIN is decoded as ASCII."""
        service = ReadDataByIdentifier(client, build_registry(config.did_definitions()))
        values = service.execute(0xF190)
        assert len(values) == 1
        assert values[0].name == "VIN"
        assert values[0].parsed.startswith("WBA")

    def test_multi_did_split(self, client, config) -> None:
        """Several identifiers are split using the known lengths."""
        service = ReadDataByIdentifier(client, build_registry(config.did_definitions()))
        values = service.execute(0xF190, 0xF18C)
        assert [value.did for value in values] == [0xF190, 0xF18C]
        assert len(values[0].raw) == 17

    def test_unknown_did_returns_none(self, client) -> None:
        """Reading an unsupported DID returns ``None``."""
        assert ReadDataByIdentifier(client).read_one(0xFFFF) is None

    def test_read_many_falls_back_to_single(self, client, config) -> None:
        """A batch containing an unknown DID still returns the known ones."""
        service = ReadDataByIdentifier(client, build_registry(config.did_definitions()))
        values = service.read_many([0xF190, 0xFFFF, 0xF18C], batch_size=3)
        assert {value.did for value in values} == {0xF190, 0xF18C}

    def test_identification_block(self, client, config) -> None:
        """The identification helper returns readable values."""
        service = ReadDataByIdentifier(client, build_registry(config.did_definitions()))
        identification = service.read_identification()
        assert "VIN" in identification


class TestDTCServices:
    """ReadDTCInformation (0x19) and ClearDiagnosticInformation (0x14)."""

    def test_read_by_status_mask(self, client) -> None:
        """Every simulated DTC is reported."""
        report = ReadDTCInformation(client).read_by_status_mask()
        assert len(report) == 3
        assert report.status_availability_mask == 0xFF

    def test_count(self, client) -> None:
        """The count sub-function matches the list length."""
        service = ReadDTCInformation(client)
        assert service.count_by_status_mask() == len(service.read_by_status_mask())

    def test_confirmed_filter(self, client) -> None:
        """Filtering by the confirmed bit reduces the list."""
        service = ReadDTCInformation(client)
        confirmed = service.read_confirmed()
        assert all(dtc.status.confirmed for dtc in confirmed)

    def test_clear_removes_every_dtc(self, client) -> None:
        """Clearing empties the fault memory."""
        result = ClearDiagnosticInformation(client).clear_all()
        assert result.accepted
        assert result.cleared_count == 3
        assert len(ReadDTCInformation(client).read_by_status_mask()) == 0

    def test_snapshot(self, client) -> None:
        """A freeze frame can be read for a known DTC."""
        report = ReadDTCInformation(client).read_by_status_mask()
        dtc = ReadDTCInformation(client).read_snapshot(report.dtcs[0].code)
        assert dtc.code == report.dtcs[0].code
        assert dtc.snapshots

    def test_extended_data(self, client) -> None:
        """Extended records carry the occurrence counter."""
        report = ReadDTCInformation(client).read_by_status_mask()
        dtc = ReadDTCInformation(client).read_extended(report.dtcs[0].code)
        assert dtc.extended_records


class TestDTCParsing:
    """DTC code helpers."""

    @pytest.mark.parametrize(
        ("code", "text"), [(0xC07300, "C0730"), (0x010000, "01000"), (0xFFFFF0, "FFFFF")]
    )
    def test_format(self, code: int, text: str) -> None:
        """The five digit rendering drops the failure type nibble."""
        assert format_dtc(code) == text

    def test_sae_round_trip(self) -> None:
        """SAE codes convert back and forth."""
        assert to_sae_code(from_sae_code("P0100")) == "P0100"
        assert to_sae_code(from_sae_code("U0100")) == "U0100"

    def test_invalid_sae_code(self) -> None:
        """A malformed code raises."""
        with pytest.raises(ValueError):
            from_sae_code("XYZ")

    def test_parse_dtc_list(self) -> None:
        """Records of four bytes are decoded into DTC objects."""
        dtcs = parse_dtc_list(bytes.fromhex("C073002F01000024"))
        assert len(dtcs) == 2
        assert dtcs[0].status.confirmed
        assert dtcs[1].status.pending

    def test_status_mask(self) -> None:
        """Masks combine the individual bits."""
        mask = StatusMask.from_bits(confirmed=True, pending=True)
        assert int(mask) == 0x0C
        assert mask.matches(0x08)
        assert not mask.matches(0x01)


class TestSecurity:
    """SecurityAccess (0x27)."""

    def test_unlock(self, client) -> None:
        """The built-in algorithm unlocks the simulator."""
        DiagnosticSessionControl(client).enter_extended()
        result = SecurityAccess(client, "xor_complement").execute(0x01)
        assert result.unlocked
        assert result.seed and result.key

    def test_wrong_algorithm_fails(self, client) -> None:
        """A mismatching algorithm is rejected by the ECU."""
        DiagnosticSessionControl(client).enter_extended()
        result = SecurityAccess(client, "add_constant").execute(0x01)
        assert not result.unlocked
        assert "invalidKey" in result.message

    def test_default_session_refuses(self, client) -> None:
        """Security access is not available in the default session."""
        result = SecurityAccess(client).execute(0x01)
        assert not result.unlocked

    @pytest.mark.parametrize(
        "algorithm", ["xor_complement", "bitwise_not", "add_constant", "xor_key", "crc_based"]
    )
    def test_algorithms_produce_same_length(self, algorithm: str) -> None:
        """Every built-in algorithm keeps the seed length."""
        seed = bytes.fromhex("A3F20188")
        assert len(compute_key(algorithm, seed)) == len(seed)


class TestControlServices:
    """RoutineControl, IOControl and ECUReset."""

    def test_routine_start(self, client) -> None:
        """Starting a routine is accepted."""
        DiagnosticSessionControl(client).enter_extended()
        result = RoutineControl(client).start(0x0202)
        assert result.accepted
        assert result.routine_id == 0x0202

    def test_io_control(self, client) -> None:
        """A short term adjustment is accepted in the extended session."""
        DiagnosticSessionControl(client).enter_extended()
        result = InputOutputControlByIdentifier(client).adjust(0xF1A0, b"\x01")
        assert result.accepted

    def test_ecu_reset(self, client) -> None:
        """The ECU accepts a hard reset."""
        result = ECUReset(client).execute(0x01, wait_s=0.0, verify=False)
        assert result.accepted
        assert result.type_name == "hardReset"


class TestTransfer:
    """Upload and download services."""

    def test_block_sequence_counter(self) -> None:
        """The counter starts at one and wraps at 255."""
        counter = BlockSequenceCounter()
        assert counter.next() == 1
        counter.value = 0xFF
        assert counter.next() == 0

    def test_counter_verification(self) -> None:
        """A wrong echo raises."""
        counter = BlockSequenceCounter()
        counter.next()
        with pytest.raises(TransferError):
            counter.verify(9)

    def test_full_download(self, client) -> None:
        """A complete flash sequence transfers every byte."""
        DiagnosticSessionControl(client).enter_extended()
        DiagnosticSessionControl(client).enter_programming()
        assert SecurityAccess(client, "add_constant").execute(0x11).unlocked
        payload = bytes(i & 0xFF for i in range(2048))
        report = TransferManager(client).download(0x08000000, payload)
        assert report.successful
        assert report.bytes_transferred == len(payload)
        assert report.crc32 is not None

    def test_download_requires_security(self, client) -> None:
        """Without an unlock the ECU refuses the download."""
        DiagnosticSessionControl(client).enter_extended()
        DiagnosticSessionControl(client).enter_programming()
        report = TransferManager(client).download(0x08000000, bytes(16))
        assert not report.successful

    def test_progress_callback(self, client) -> None:
        """The progress callback is invoked for every block."""
        DiagnosticSessionControl(client).enter_extended()
        DiagnosticSessionControl(client).enter_programming()
        SecurityAccess(client, "add_constant").execute(0x11)
        samples: list[float] = []
        manager = TransferManager(client, on_progress=lambda p: samples.append(p.percent))
        manager.download(0x08000000, bytes(3000))
        assert samples and samples[-1] == pytest.approx(100.0)
