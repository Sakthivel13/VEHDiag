"""Tests for the pure helper functions of the panel and dialog modules.

These cover the request builders, validators and formatters that back the
diagnostic, developer, log, settings and dialog widgets. They need no
``QApplication`` beyond the session fixture because every function under test
is free of Qt state.
"""
from __future__ import annotations

import pytest

from src.communication.connection_manager import ConnectionProfile
from src.core.models.did_model import DIDValue
from src.core.models.dtc_model import DTC, DTCSnapshotRecord, DTCStatus
from src.core.models.file_transfer_model import MemorySegment, TransferFile
from src.core.models.log_entry_model import LogEntry, LogLevel
from src.core.models.test_sequence_model import TestSequence, TestStep
from src.data_processing.file_parsers.memory_map import MemoryMap
from src.logging_system.log_filter import LogFilter


# -- session control ---------------------------------------------------------
class TestSessionTypeSelectorHelpers:
    """Validation rules of the session sub-function selector."""

    @pytest.mark.parametrize("value", [0x01, 0x02, 0x03, 0x04, 0x4F, 0x60])
    def test_accepts_valid_sessions(self, value: int) -> None:
        """Standard, manufacturer and supplier sessions are accepted."""
        from ui.panels.diagnostic_panel.session_control_panel.session_type_selector import (
            validate_sub_function,
        )

        assert validate_sub_function(value) == (True, "")

    @pytest.mark.parametrize("value", [0x00, 0x7F, 0x10, 0x3F])
    def test_rejects_invalid_sessions(self, value: int) -> None:
        """Reserved and out-of-range sub-functions are rejected with a reason."""
        from ui.panels.diagnostic_panel.session_control_panel.session_type_selector import (
            validate_sub_function,
        )

        valid, reason = validate_sub_function(value)
        assert not valid
        assert reason

    def test_choices_cover_the_standard_sessions(self) -> None:
        """The drop-down offers the four ISO sessions."""
        from ui.panels.diagnostic_panel.session_control_panel.session_type_selector import (
            session_choices,
        )

        assert [value for value, _ in session_choices()] == [1, 2, 3, 4]


class TestSessionStatusHelpers:
    """S3 countdown formatting and classification."""

    def test_format_remaining(self) -> None:
        """Sub-second values keep the millisecond unit."""
        from ui.panels.diagnostic_panel.session_control_panel.session_status_display import (
            format_remaining,
        )

        assert format_remaining(0) == "expired"
        assert format_remaining(250) == "250 ms"
        assert format_remaining(2500) == "2.5 s"

    @pytest.mark.parametrize(
        "remaining,expected",
        [(4000.0, "ok"), (800.0, "warning"), (100.0, "error"), (0.0, "error")],
    )
    def test_timer_state(self, remaining: float, expected: str) -> None:
        """The countdown is classified against the configured S3 time."""
        from ui.panels.diagnostic_panel.session_control_panel.session_status_display import (
            timer_state,
        )

        assert timer_state(remaining, 4000.0) == expected


# -- read DID ----------------------------------------------------------------
class TestDIDHelpers:
    """Parsing, chunking and rendering of data identifiers."""

    def test_parse_did_text_handles_separators_and_duplicates(self) -> None:
        """Commas, semicolons and whitespace all separate identifiers."""
        from ui.panels.diagnostic_panel.read_did_panel.did_selector import parse_did_text

        assert parse_did_text("F190, 0xF18C; F187 F190") == [0xF190, 0xF18C, 0xF187]

    def test_parse_did_text_ignores_garbage(self) -> None:
        """Tokens that are not hexadecimal are dropped."""
        from ui.panels.diagnostic_panel.read_did_panel.did_selector import parse_did_text

        assert parse_did_text("F190 zzz G1") == [0xF190]

    def test_chunking_preserves_order(self) -> None:
        """Chunks keep the requested order and never exceed the size."""
        from ui.panels.diagnostic_panel.read_did_panel.did_batch_reader import chunk_dids

        chunks = chunk_dids(range(10), 3)
        assert chunks == [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]]
        assert all(len(chunk) <= 3 for chunk in chunks)

    def test_estimate_response_size_uses_known_lengths(self) -> None:
        """A known length replaces the default eight byte assumption."""
        from ui.panels.diagnostic_panel.read_did_panel.did_batch_reader import (
            estimate_response_size,
        )

        assert estimate_response_size([0xF190], {0xF190: 17}) == 1 + 2 + 17

    def test_physical_value_applies_factor_and_offset(self) -> None:
        """The physical conversion follows ``raw * factor + offset``."""
        from ui.panels.diagnostic_panel.read_did_panel.did_response_display import (
            physical_value,
        )

        assert physical_value(b"\x64", factor=0.5, offset=-10.0) == 40.0
        assert physical_value(b"\xff", signed=True) == -1.0
        assert physical_value(b"") is None

    def test_summarise_renders_hex_and_ascii(self) -> None:
        """The status line shows both the hex and the ASCII rendering."""
        from ui.panels.diagnostic_panel.read_did_panel.did_response_display import summarise

        text = summarise(DIDValue(did=0xF190, raw=b"AB"))
        assert "F190" in text and "4142" in text and '"AB"' in text


# -- read / clear DTC --------------------------------------------------------
class TestDTCHelpers:
    """Request building and status decoding for the DTC services."""

    def test_build_request_appends_only_required_fields(self) -> None:
        """Sub-function 0x0A needs no parameter at all."""
        from ui.panels.diagnostic_panel.read_dtc_panel.dtc_subfunction_selector import (
            build_request,
        )

        assert build_request(0x0A) == bytes.fromhex("190A")
        assert build_request(0x02, status_mask=0xFF) == bytes.fromhex("1902FF")
        assert build_request(0x06, dtc=0xC07300, record_number=1) == bytes.fromhex(
            "1906C0730001"
        )

    def test_required_fields_match_the_specification(self) -> None:
        """Sub-function 0x19 needs a memory selector, a DTC and a record."""
        from ui.panels.diagnostic_panel.read_dtc_panel.dtc_subfunction_selector import (
            required_fields,
        )

        assert required_fields(0x19) == {"dtc", "memory_selection", "record_number"}

    def test_bit_rows_follow_the_iso_order(self) -> None:
        """Bit 0 is testFailed and bit 7 is warningIndicatorRequested."""
        from ui.panels.diagnostic_panel.read_dtc_panel.dtc_status_display import bit_rows

        rows = bit_rows(0xFF)
        assert rows[0]["name"] == "testFailed"
        assert rows[7]["name"] == "warningIndicatorRequested"
        assert all(row["set"] for row in rows)

    @pytest.mark.parametrize(
        "status,severity",
        [(0x08, "confirmed"), (0x04, "pending"), (0x80, "warning"), (0x00, "clean")],
    )
    def test_severity_classification(self, status: int, severity: str) -> None:
        """Confirmed wins over pending, which wins over the warning lamp."""
        from ui.panels.diagnostic_panel.read_dtc_panel.dtc_status_display import severity_of

        assert severity_of(status) == severity

    def test_dtc_to_row_colours_by_severity(self) -> None:
        """A confirmed DTC is rendered in the error colour."""
        from ui.panels.diagnostic_panel.read_dtc_panel.dtc_table_view import dtc_to_row

        row = dtc_to_row(DTC(code=0xC07300, status=DTCStatus(0x2F), name="Sensor"))
        assert row["Code"] == "C0730"
        assert row["Confirmed"] == "yes"
        assert row["_color"] == "#EF4444"

    def test_category_and_failure_type(self) -> None:
        """The category comes from the two most significant bits."""
        from ui.panels.diagnostic_panel.read_dtc_panel.dtc_detail_view import (
            category_name,
            describe_failure_type,
        )

        assert category_name(0xC07300) == "Network"
        assert category_name(0x010000) == "Powertrain"
        assert describe_failure_type(0x11) == "circuit short to ground"
        assert "manufacturer specific" in describe_failure_type(0xAB)

    def test_decode_snapshot_uses_length_prefix(self) -> None:
        """Unknown identifiers fall back to the explicit length byte."""
        from ui.panels.diagnostic_panel.read_dtc_panel.dtc_freeze_frame_view import (
            decode_snapshot,
        )

        items = decode_snapshot(bytes.fromhex("F190024142"), {})
        assert items[0]["did"] == 0xF190
        assert items[0]["ascii"] == "AB"

    def test_split_records_keeps_the_payload(self) -> None:
        """The record number is stripped and the payload is kept intact."""
        from ui.panels.diagnostic_panel.read_dtc_panel.dtc_freeze_frame_view import (
            split_records,
        )

        records = split_records(bytes.fromhex("0101F1900141"))
        assert records[0].record_number == 1
        assert records[0].data == bytes.fromhex("F1900141")

    def test_group_masks(self) -> None:
        """Each group maps to the first value of its range."""
        from ui.panels.diagnostic_panel.clear_dtc_panel.dtc_group_selector import mask_for

        assert mask_for("all") == 0xFFFFFF
        assert mask_for("chassis") == 0x400000
        assert mask_for("network") == 0xC00000

    def test_clear_confirmation_wording(self) -> None:
        """Clearing everything needs the extra acknowledgement."""
        from ui.panels.diagnostic_panel.clear_dtc_panel.clear_confirmation import (
            confirmation_text,
            requires_double_confirmation,
            warnings_for,
        )

        assert requires_double_confirmation(0xFFFFFF)
        assert not requires_double_confirmation(0x400000)
        assert "3 code(s)" in confirmation_text(0xFFFFFF, 3)
        assert any("cannot be undone" in w for w in warnings_for(0xFFFFFF))


# -- security access ---------------------------------------------------------
class TestSecurityHelpers:
    """Seed/key level pairing and rendering."""

    def test_request_and_send_levels_pair_up(self) -> None:
        """An odd requestSeed level pairs with the following even sendKey."""
        from ui.panels.diagnostic_panel.security_access_panel.security_level_selector import (
            request_seed_level,
            send_key_level,
        )

        for level in (0x01, 0x03, 0x05, 0x0B):
            assert send_key_level(level) == level + 1
            assert request_seed_level(level + 1) == level

    def test_even_levels_are_rejected(self) -> None:
        """A sendKey sub-function cannot be used to request a seed."""
        from ui.panels.diagnostic_panel.security_access_panel.security_level_selector import (
            validate_level,
        )

        valid, reason = validate_level(0x02)
        assert not valid
        assert "sendKey" in reason

    def test_all_zero_seed_means_unlocked(self) -> None:
        """An all-zero seed is the ISO way of saying "already unlocked"."""
        from ui.panels.diagnostic_panel.security_access_panel.seed_key_display import (
            is_already_unlocked,
        )

        assert is_already_unlocked(b"\x00\x00\x00\x00")
        assert not is_already_unlocked(b"\x00\x01")
        assert not is_already_unlocked(b"")

    def test_source_requires_a_path_only_for_files(self) -> None:
        """Built-in and manual sources need no file."""
        from src.diagnostics.services.security.security_dll_loader import AlgorithmSource
        from ui.panels.diagnostic_panel.security_access_panel.security_dll_config import (
            needs_path,
        )

        assert needs_path(AlgorithmSource.SHARED_LIBRARY)
        assert needs_path(AlgorithmSource.PYTHON_SCRIPT)
        assert not needs_path(AlgorithmSource.BUILTIN)
        assert not needs_path(AlgorithmSource.MANUAL)


# -- transfer ----------------------------------------------------------------
class TestTransferHelpers:
    """File type detection, memory layout and progress formatting."""

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("a.hex", "INTEL_HEX"),
            ("a.S19", "SREC"),
            ("a.mot", "SREC"),
            ("a.bin", "BINARY"),
            ("a.elf", "ELF"),
            ("a.txt", "UNKNOWN"),
        ],
    )
    def test_detect_type(self, name: str, expected: str) -> None:
        """The suffix determines the firmware file type, case insensitively."""
        from ui.panels.diagnostic_panel.transfer_panel.file_selector_panel import detect_type

        assert detect_type(name).value == expected

    def test_file_row_reports_the_address_range(self) -> None:
        """The row shows the start, the end and the human readable size."""
        from pathlib import Path

        from ui.panels.diagnostic_panel.transfer_panel.file_selector_panel import file_row

        entry = TransferFile(
            Path("fw.bin"), segments=[MemorySegment(0x8000, b"\x00" * 32)]
        )
        row = file_row(0, entry)
        assert row["Start"] == "0x00008000"
        assert row["End"] == "0x00008020"
        assert row["Enabled"] == "yes"

    def test_segment_bars_are_normalised(self) -> None:
        """Bar geometry is expressed as fractions of the whole span."""
        from ui.panels.diagnostic_panel.transfer_panel.memory_layout_view import segment_bars

        memory = MemoryMap()
        memory.add(MemorySegment(0x0000, b"\x00" * 256))
        memory.add(MemorySegment(0x0200, b"\x00" * 256))
        bars = segment_bars(memory)
        assert len(bars) == 2
        assert bars[0]["start_fraction"] == pytest.approx(0.0)
        assert bars[1]["start_fraction"] == pytest.approx(2 / 3, abs=1e-3)

    def test_segment_rows_interleave_the_gaps(self) -> None:
        """Gaps appear between the segments they separate."""
        from ui.panels.diagnostic_panel.transfer_panel.memory_layout_view import segment_rows

        memory = MemoryMap()
        memory.add(MemorySegment(0x0000, b"\x00" * 16))
        memory.add(MemorySegment(0x0100, b"\x00" * 16))
        assert [row["Kind"] for row in segment_rows(memory)] == ["segment", "gap", "segment"]

    def test_phase_index(self) -> None:
        """Free-form phase names are mapped onto the ordered phase list."""
        from ui.panels.diagnostic_panel.transfer_panel.transfer_progress_view import phase_index

        assert phase_index("Request download") == 1
        assert phase_index("Transferring data") == 2
        assert phase_index("Verifying CRC") == 4
        assert phase_index("nonsense") == 0

    def test_block_count_rounds_up(self) -> None:
        """A partial final block still counts."""
        from ui.dialogs.file_transfer_dialog import block_count

        assert block_count(2048, 1024) == 2
        assert block_count(2049, 1024) == 3
        assert block_count(0, 1024) == 0

    def test_validate_request(self) -> None:
        """A zero size or block size is rejected with an explanation."""
        from ui.dialogs.file_transfer_dialog import validate_request

        assert validate_request(1024, 512) == (True, "")
        assert not validate_request(0, 512)[0]
        assert not validate_request(1024, 0)[0]


# -- service tab manager -----------------------------------------------------
class TestServiceTabManager:
    """Availability rules of the diagnostic tabs."""

    def test_everything_is_disabled_while_disconnected(self) -> None:
        """Without a transport no tab may be used."""
        from ui.panels.diagnostic_panel.service_tab_manager import ServiceTabManager

        manager = ServiceTabManager()
        assert manager.enabled_titles() == []

    def test_session_tab_is_available_right_after_connecting(self) -> None:
        """The session tab must work in the default session."""
        from ui.panels.diagnostic_panel.service_tab_manager import ServiceTabManager

        manager = ServiceTabManager()
        manager.set_connected(True)
        assert "Session" in manager.enabled_titles()
        assert manager.first_enabled() == "Session"

    def test_flash_requires_security(self) -> None:
        """RequestDownload stays disabled until security access is granted."""
        from ui.panels.diagnostic_panel.service_tab_manager import evaluate_tab

        state = evaluate_tab("Flash / transfer", connected=True, session=3, unlocked=False)
        assert not state.enabled
        assert state.reason == "Requires security access"
        assert evaluate_tab(
            "Flash / transfer", connected=True, session=3, unlocked=True
        ).enabled

    def test_disconnecting_clears_the_session_and_security(self) -> None:
        """Losing the link resets the remembered ECU state."""
        from ui.panels.diagnostic_panel.service_tab_manager import ServiceTabManager

        manager = ServiceTabManager()
        manager.set_connected(True)
        manager.set_session(3)
        manager.set_unlocked(True)
        manager.set_connected(False)
        assert manager.session == 1
        assert not manager.unlocked


# -- developer mode ----------------------------------------------------------
class TestDeveloperHelpers:
    """Payload composition, script templates and the mapping file."""

    def test_compose_prefixes_the_sid(self) -> None:
        """The request is the SID followed by the parameter bytes."""
        from ui.panels.developer_panel.payload_entry_widget import compose

        assert compose(0x22, b"\xf1\x90") == bytes.fromhex("22F190")

    def test_validate_payload_enforces_the_minimum_length(self) -> None:
        """ReadDataByIdentifier needs a two byte identifier."""
        from ui.panels.developer_panel.payload_entry_widget import validate_payload

        assert validate_payload(0x22, b"\xf1\x90") == (True, "")
        assert not validate_payload(0x22, b"\xf1")[0]
        assert validate_payload(0x99, b"") == (True, "")

    def test_suggested_filename_slugifies_the_name(self) -> None:
        """The script name is derived from the SID and the service name."""
        from ui.panels.developer_panel.test_file_mapper import suggested_filename

        assert suggested_filename(0x2E, "Write Data By ID") == "test_2e_write_data_by_id.py"
        assert suggested_filename(0x27) == "test_27.py"

    def test_mapping_round_trips_through_yaml(self, tmp_path) -> None:
        """A saved mapping reloads with the same script paths."""
        from ui.panels.developer_panel.test_file_mapper import TestFileMapping

        mapping = TestFileMapping()
        mapping.assign(0x10, "/tmp/session.py", "Session Control")
        mapping.assign(0x22, "/tmp/read_did.py")
        target = mapping.save(tmp_path / "mapping.yaml")
        reloaded = TestFileMapping.load(target)
        assert reloaded.script_for(0x10) == "/tmp/session.py"
        assert reloaded.service_name(0x10) == "Session Control"

    def test_mapping_from_sequence(self) -> None:
        """Only the steps carrying a script contribute to the mapping."""
        from ui.panels.developer_panel.test_file_mapper import mapping_from_sequence

        sequence = TestSequence(
            steps=[
                TestStep(0x10, "Session", script_path="s.py"),
                TestStep(0x22, "Read DID"),
            ]
        )
        mapping = mapping_from_sequence(sequence)
        assert len(mapping) == 1
        assert mapping.script_for(0x10) == "s.py"

    def test_default_template_is_valid(self) -> None:
        """The generated template passes the script validator."""
        from src.test_execution.scripts.script_validator import ScriptValidator
        from ui.panels.developer_panel.script_editor_panel import default_template

        report = ScriptValidator(strict=False).validate_source(default_template(0x22, "Read"))
        assert report.valid, report.summary()

    def test_run_all_summary(self) -> None:
        """The summary only mentions the non-zero counters."""
        from ui.panels.developer_panel.run_all_button import summary_text

        assert summary_text(3, 1, 0) == "3 passed, 1 failed"
        assert summary_text(0, 0, 0) == "nothing executed"

    def test_watched_variable_tracks_changes(self) -> None:
        """Recording the same value twice counts as one change."""
        from ui.panels.developer_panel.variable_watch_panel import WatchedVariable

        variable = WatchedVariable("vin")
        assert variable.update("A")
        assert not variable.update("A")
        assert variable.update("B")
        assert variable.changes == 2
        assert list(variable.history) == ["A", "B"]


# -- log panel ---------------------------------------------------------------
class TestLogHelpers:
    """Filter description, search and export naming."""

    def test_parse_id_accepts_both_notations(self) -> None:
        """``0x7E0`` and ``7E0`` parse to the same value."""
        from ui.panels.log_panel.log_filter_panel import parse_id

        assert parse_id("0x7E0") == parse_id("7E0") == 0x7E0
        assert parse_id("") is None
        assert parse_id("zz") is None

    def test_describe_filter_lists_the_active_criteria(self) -> None:
        """An empty filter is reported as inactive."""
        from ui.panels.log_panel.log_filter_panel import describe_filter

        assert describe_filter(LogFilter()) == "no filter active"
        text = describe_filter(LogFilter(min_level=LogLevel.ERROR, contains="7E8"))
        assert "level >= ERROR" in text and "contains '7E8'" in text

    def test_find_matches_respects_the_options(self) -> None:
        """Case sensitivity, regex and whole-word all change the result."""
        from ui.panels.log_panel.log_search_panel import SearchOptions, find_matches

        entries = [LogEntry(message="Hello"), LogEntry(message="hello world")]
        assert find_matches(entries, "hello") == [0, 1]
        assert find_matches(entries, "hello", SearchOptions(case_sensitive=True)) == [1]
        assert find_matches(entries, "h.llo", SearchOptions(regex=True)) == [0, 1]
        assert find_matches(entries, "hell", SearchOptions(whole_word=True)) == []

    def test_find_matches_survives_a_broken_regex(self) -> None:
        """An invalid expression yields no match instead of raising."""
        from ui.panels.log_panel.log_search_panel import SearchOptions, find_matches

        assert find_matches([LogEntry(message="x")], "[", SearchOptions(regex=True)) == []

    def test_next_index_wraps_around(self) -> None:
        """Navigation wraps at both ends of the match list."""
        from ui.panels.log_panel.log_search_panel import next_index

        assert next_index([2, 5, 9], 5, forward=True) == 9
        assert next_index([2, 5, 9], 9, forward=True) == 2
        assert next_index([2, 5, 9], 2, forward=False) == 9
        assert next_index([], 0) == -1

    def test_default_filename_uses_the_format_suffix(self) -> None:
        """Each format contributes its conventional suffix."""
        from ui.panels.log_panel.log_export_dialog import default_filename

        assert default_filename("CSV").endswith(".csv")
        assert default_filename("HTML").endswith(".html")
        assert default_filename("BLF", "s7").startswith("vdp_log_s7_")


# -- settings and dialogs ----------------------------------------------------
class TestSettingsAndDialogHelpers:
    """Specs, previews and dialog validation."""

    def test_every_settings_page_declares_unique_paths(self) -> None:
        """No configuration path is edited by two pages."""
        from ui.panels.settings_panel import (
            display_settings,
            general_settings,
            logging_settings,
            plugin_settings,
            protocol_settings,
        )

        for module in (
            general_settings,
            protocol_settings,
            display_settings,
            logging_settings,
            plugin_settings,
        ):
            paths = module.paths()
            assert len(paths) == len(set(paths)), module.__name__

    def test_display_preview_names_the_palette_colours(self) -> None:
        """The preview quotes the exact palette colours of the theme."""
        from ui.panels.settings_panel.display_settings import preview_text

        assert "#1E1E2E" in preview_text("dark")
        assert "#7C3AED" in preview_text("light")
        assert preview_text("nope") == "unknown theme"

    def test_logging_disk_estimate(self) -> None:
        """The estimate covers the active file plus every rotated one."""
        from ui.panels.settings_panel.logging_settings import estimate_disk_usage

        assert estimate_disk_usage(10, 3).startswith("40 MB")

    def test_parse_directories(self) -> None:
        """Empty entries are dropped and the rest is stripped."""
        from ui.panels.settings_panel.plugin_settings import parse_directories

        assert parse_directories(" a , , b ") == ["a", "b"]
        assert parse_directories("") == []

    def test_changed_paths(self) -> None:
        """Only the differing paths are reported."""
        from ui.dialogs.preferences_dialog import changed_paths

        assert changed_paths({"a": 1, "b": 2}, {"a": 1, "b": 3}) == ["b"]

    def test_default_ids_per_protocol(self) -> None:
        """CAN, J1939 and DoIP each get their conventional identifiers."""
        from ui.dialogs.vci_config_dialog import default_ids

        assert default_ids("CAN") == (0x7E0, 0x7E8, 0x7DF)
        assert default_ids("J1939")[0] == 0xF9
        assert default_ids("DOIP")[1] == 0x0E00

    def test_validate_profile(self) -> None:
        """Identical request and response identifiers are rejected."""
        from ui.dialogs.vci_config_dialog import validate_profile

        assert validate_profile(ConnectionProfile()) == (True, "")
        assert not validate_profile(ConnectionProfile(tx_id=0x7E0, rx_id=0x7E0))[0]
        assert not validate_profile(ConnectionProfile(bitrate=0))[0]
        assert not validate_profile(ConnectionProfile(tx_id=0x800, extended_id=False))[0]

    def test_vin_validation_and_decoding(self) -> None:
        """A VIN is 17 characters and excludes I, O and Q."""
        from ui.dialogs.ecu_identification_dialog import decode_vin, is_valid_vin

        assert is_valid_vin("WBAZZZ0GM12345678")
        assert not is_valid_vin("WBAZZZ0GM1234567")
        assert not is_valid_vin("IBAZZZ0GM12345678")
        decoded = decode_vin("WBAZZZ0GM12345678")
        assert decoded["wmi"] == "WBA"
        assert decoded["vis"] == "M12345678"
        assert decode_vin("bad")["valid"] == "no"

    def test_report_renderers_include_the_sections(self) -> None:
        """Each renderer honours the selected sections."""
        from ui.dialogs.report_generator_dialog import (
            ReportData,
            render_html,
            render_markdown,
            render_text,
        )

        data = ReportData(
            title="Session",
            ecu_name="ECM",
            identification={"VIN": "WBAZZZ0GM12345678"},
            dtcs=[DTC(code=0xC07300, status=DTCStatus(0x2F), name="Sensor")],
            dids=[DIDValue(did=0xF190, raw=b"WBA")],
        )
        text = render_text(data)
        assert "C0730" in text and "WBAZZZ0GM12345678" in text
        assert render_markdown(data).startswith("# Session")
        html = render_html(data)
        assert html.startswith("<!DOCTYPE html>") and "C0730" in html

    def test_report_sections_can_be_excluded(self) -> None:
        """Deselecting a section removes it from the output."""
        from ui.dialogs.report_generator_dialog import ReportData, render_text

        data = ReportData(dtcs=[DTC(code=0x010000, status=DTCStatus(0x08))])
        assert "Diagnostic trouble codes" not in render_text(data, sections=["dids"])
        assert "Diagnostic trouble codes" in render_text(data, sections=["dtcs"])


# -- responsive styles -------------------------------------------------------
class TestResponsiveStyles:
    """Breakpoint dependent geometry."""

    def test_metrics_grow_with_the_breakpoint(self) -> None:
        """Wider layouts get taller controls and more spacing."""
        from ui.responsive_layout import Breakpoint
        from ui.styles.responsive_styles import control_metrics

        heights = [
            control_metrics(bp).control_height
            for bp in (
                Breakpoint.COMPACT,
                Breakpoint.STANDARD,
                Breakpoint.WIDE,
                Breakpoint.ULTRA_WIDE,
            )
        ]
        assert heights == sorted(heights)
        assert len(set(heights)) == 4

    def test_stylesheet_scales_with_the_dpi_factor(self) -> None:
        """Doubling the scale doubles the emitted pixel values."""
        from ui.responsive_layout import Breakpoint
        from ui.styles.responsive_styles import responsive_stylesheet

        single = responsive_stylesheet(Breakpoint.STANDARD, 1.0)
        double = responsive_stylesheet(Breakpoint.STANDARD, 2.0)
        assert "min-height: 30px" in single
        assert "min-height: 60px" in double

    def test_density_names(self) -> None:
        """Each breakpoint maps to a distinct QSS density class."""
        from ui.responsive_layout import Breakpoint
        from ui.styles.responsive_styles import density_name

        names = {density_name(bp) for bp in Breakpoint}
        assert names == {"compact", "standard", "comfortable", "spacious"}
