"""Widget level tests for the diagnostic, developer, log and settings panels.

Each test builds a real widget with ``qtbot`` and drives it through its public
API, checking the emitted signals and the rendered state.
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402

from src.core.models.did_model import DIDDefinition, DIDRegistry, DIDValue  # noqa: E402
from src.core.models.dtc_model import (  # noqa: E402
    DTC,
    DTCExtendedRecord,
    DTCReport,
    DTCSnapshotRecord,
    DTCStatus,
)
from src.core.models.ecu_model import ECU, ECUIdentification  # noqa: E402
from src.core.models.file_transfer_model import (  # noqa: E402
    MemorySegment,
    TransferProgress,
)
from src.core.models.log_entry_model import LogEntry, LogLevel  # noqa: E402
from src.core.models.session_model import SessionState, SessionTiming  # noqa: E402
from src.core.models.test_sequence_model import (  # noqa: E402
    TestResult,
    TestSequence,
    TestStatus,
    TestStep,
)

pytestmark = pytest.mark.ui


# -- session control ---------------------------------------------------------
class TestSessionTypeSelector:
    """The session drop-down and its custom entry."""

    def test_default_selection_is_extended(self, qtbot, scaler) -> None:
        """The extended session is preselected as the most common choice."""
        from ui.panels.diagnostic_panel.session_control_panel import SessionTypeSelector

        widget = SessionTypeSelector(scaler=scaler)
        qtbot.addWidget(widget)
        assert widget.session() == 0x03
        assert widget.is_valid()

    def test_custom_entry_accepts_a_manufacturer_session(self, qtbot, scaler) -> None:
        """Selecting an unknown value switches to the custom hex field."""
        from ui.panels.diagnostic_panel.session_control_panel import SessionTypeSelector

        widget = SessionTypeSelector(scaler=scaler)
        qtbot.addWidget(widget)
        widget.set_session(0x4F)
        assert widget.custom_field.isVisible() or widget.session() == 0x4F
        assert widget.session() == 0x4F
        assert widget.is_valid()

    def test_signal_is_emitted_on_change(self, qtbot, scaler) -> None:
        """Choosing a session publishes it."""
        from ui.panels.diagnostic_panel.session_control_panel import SessionTypeSelector

        widget = SessionTypeSelector(scaler=scaler)
        qtbot.addWidget(widget)
        with qtbot.waitSignal(widget.session_changed, timeout=1000) as blocker:
            widget.set_session(0x02)
        assert blocker.args == [0x02]


class TestSessionStatusDisplay:
    """The session, security and S3 countdown display."""

    def test_updates_every_field(self, qtbot, scaler) -> None:
        """The labels reflect the handed-in session state."""
        from ui.panels.diagnostic_panel.session_control_panel import SessionStatusDisplay

        widget = SessionStatusDisplay(scaler=scaler, auto_tick=False)
        qtbot.addWidget(widget)
        widget.update_state(
            SessionState(active_session=0x03, timing=SessionTiming(p2_server_ms=50.0))
        )
        assert "0x03" in widget.session_label.text()
        assert widget.p2_label.text() == "50 ms"
        assert widget.keepalive_label.text() == "required"
        assert widget.remaining_ms() > 0

    def test_default_session_needs_no_keepalive(self, qtbot, scaler) -> None:
        """The countdown is hidden in the default session."""
        from ui.panels.diagnostic_panel.session_control_panel import SessionStatusDisplay

        widget = SessionStatusDisplay(scaler=scaler, auto_tick=False)
        qtbot.addWidget(widget)
        widget.update_state(SessionState(active_session=0x01))
        assert widget.keepalive_label.text() == "not required"
        assert widget.remaining_ms() == 0.0


# -- read DID ----------------------------------------------------------------
class TestDIDSelector:
    """The searchable identifier list."""

    @pytest.fixture()
    def registry(self) -> DIDRegistry:
        """Return a registry holding three well known identifiers."""
        registry = DIDRegistry()
        registry.add(DIDDefinition(0xF190, "VIN", length=17))
        registry.add(DIDDefinition(0xF18C, "ECU serial", length=10))
        registry.add(DIDDefinition(0xF195, "Software version", length=4))
        return registry

    def test_lists_the_registry(self, qtbot, scaler, registry: DIDRegistry) -> None:
        """Every registered identifier appears in the list."""
        from ui.panels.diagnostic_panel.read_did_panel import DIDSelector

        widget = DIDSelector(scaler=scaler, registry=registry)
        qtbot.addWidget(widget)
        assert widget.list_widget.count() == 3

    def test_selection_is_reported(self, qtbot, scaler, registry: DIDRegistry) -> None:
        """The selected identifiers are exposed and published."""
        from ui.panels.diagnostic_panel.read_did_panel import DIDSelector

        widget = DIDSelector(scaler=scaler, registry=registry)
        qtbot.addWidget(widget)
        widget.select([0xF190, 0xF195])
        assert sorted(widget.selected_dids()) == [0xF190, 0xF195]

    def test_filter_hides_non_matching_rows(self, qtbot, scaler, registry: DIDRegistry) -> None:
        """Filtering narrows the visible entries."""
        from ui.panels.diagnostic_panel.read_did_panel import DIDSelector

        widget = DIDSelector(scaler=scaler, registry=registry)
        qtbot.addWidget(widget)
        assert widget.apply_filter("vin") == 1
        assert widget.apply_filter("") == 3

    def test_custom_did_is_added(self, qtbot, scaler, registry: DIDRegistry) -> None:
        """A hand typed identifier joins the registry."""
        from ui.panels.diagnostic_panel.read_did_panel import DIDSelector

        widget = DIDSelector(scaler=scaler, registry=registry)
        qtbot.addWidget(widget)
        widget.custom_field.set_value(bytes.fromhex("F1A0"))
        assert widget.add_custom() == 0xF1A0
        assert registry.get(0xF1A0) is not None


class TestDIDBatchReader:
    """The chunked batch reading state machine."""

    def test_chunks_are_requested_in_order(self, qtbot, scaler) -> None:
        """Each chunk is emitted only after the previous one answered."""
        from ui.panels.diagnostic_panel.read_did_panel import DIDBatchReader

        widget = DIDBatchReader(scaler=scaler)
        qtbot.addWidget(widget)
        widget.chunk_spin.setValue(2)
        requested: list[list[int]] = []
        widget.chunk_requested.connect(requested.append)
        widget.start([1, 2, 3, 4, 5])
        assert requested == [[1, 2]]
        widget.chunk_completed([])
        assert requested == [[1, 2], [3, 4]]
        widget.chunk_completed([])
        assert requested[-1] == [5]

    def test_failures_are_recorded_per_did(self, qtbot, scaler) -> None:
        """A failed chunk marks every identifier it contained."""
        from ui.panels.diagnostic_panel.read_did_panel import DIDBatchReader

        widget = DIDBatchReader(scaler=scaler)
        qtbot.addWidget(widget)
        widget.chunk_spin.setValue(2)
        progress = widget.start([1, 2])
        widget.chunk_failed("timeout")
        assert progress.failures == {1: "timeout", 2: "timeout"}
        assert progress.is_finished

    def test_stop_on_error_aborts_the_batch(self, qtbot, scaler) -> None:
        """With *stop on error* the remaining chunks are skipped."""
        from ui.panels.diagnostic_panel.read_did_panel import DIDBatchReader

        widget = DIDBatchReader(scaler=scaler)
        qtbot.addWidget(widget)
        widget.chunk_spin.setValue(1)
        widget.stop_on_error.setChecked(True)
        progress = widget.start([1, 2, 3])
        widget.chunk_failed("NRC 0x31")
        assert progress.is_finished

    def test_batch_finished_carries_the_values(self, qtbot, scaler) -> None:
        """The collected readings are published when the batch ends."""
        from ui.panels.diagnostic_panel.read_did_panel import DIDBatchReader

        widget = DIDBatchReader(scaler=scaler)
        qtbot.addWidget(widget)
        widget.chunk_spin.setValue(4)
        value = DIDValue(did=0xF190, raw=b"WBA")
        with qtbot.waitSignal(widget.batch_finished, timeout=1000) as blocker:
            widget.start([0xF190])
            widget.chunk_completed([value])
        assert blocker.args[0] == [value]


class TestDIDResponseDisplay:
    """The single reading detail pane."""

    def test_renders_hex_ascii_and_physical(self, qtbot, scaler) -> None:
        """All three renderings are filled from the definition."""
        from ui.panels.diagnostic_panel.read_did_panel import DIDResponseDisplay

        widget = DIDResponseDisplay(scaler=scaler)
        qtbot.addWidget(widget)
        definition = DIDDefinition(0xF1A0, "Coolant", length=1, factor=0.5, offset=-40.0, unit="C")
        widget.set_value(DIDValue(did=0xF1A0, raw=b"\x64", definition=definition))
        assert widget.hex_label.text() == "64"
        assert widget.length_label.text() == "1 bytes"
        assert widget.physical_label.text() == "10 C"

    def test_clear_resets_every_field(self, qtbot, scaler) -> None:
        """Clearing returns the pane to its empty state."""
        from ui.panels.diagnostic_panel.read_did_panel import DIDResponseDisplay

        widget = DIDResponseDisplay(scaler=scaler)
        qtbot.addWidget(widget)
        widget.set_value(DIDValue(did=0xF190, raw=b"WBA"))
        widget.clear()
        assert widget.raw() == b""
        assert widget.hex_label.text() == "-"


# -- read DTC ----------------------------------------------------------------
class TestDTCWidgets:
    """The DTC sub-function, status, table, detail and freeze frame widgets."""

    def test_subfunction_selector_reports_required_fields(self, qtbot, scaler) -> None:
        """Switching the sub-function updates the required parameter set."""
        from ui.panels.diagnostic_panel.read_dtc_panel import DTCSubFunctionSelector

        widget = DTCSubFunctionSelector(scaler=scaler)
        qtbot.addWidget(widget)
        assert widget.required_fields() == {"status_mask"}
        widget.set_sub_function(0x0A)
        assert widget.required_fields() == set()
        assert widget.returns_list()

    def test_status_display_lists_the_active_bits(self, qtbot, scaler) -> None:
        """Setting 0x2F lights five indicators."""
        from ui.panels.diagnostic_panel.read_dtc_panel import DTCStatusDisplay

        widget = DTCStatusDisplay(scaler=scaler)
        qtbot.addWidget(widget)
        widget.set_status(0x2F)
        assert widget.status() == 0x2F
        assert widget.severity() == "confirmed"
        assert len(widget.active_names()) == 5

    def test_status_display_accepts_a_dtc_status(self, qtbot, scaler) -> None:
        """A :class:`DTCStatus` may be passed directly."""
        from ui.panels.diagnostic_panel.read_dtc_panel import DTCStatusDisplay

        widget = DTCStatusDisplay(scaler=scaler)
        qtbot.addWidget(widget)
        widget.set_status(DTCStatus(0x80))
        assert widget.severity() == "warning"

    def test_table_counts_by_severity(self, qtbot, scaler) -> None:
        """The table reports how many codes fall in each class."""
        from ui.panels.diagnostic_panel.read_dtc_panel import DTCTableView

        widget = DTCTableView(scaler=scaler)
        qtbot.addWidget(widget)
        report = DTCReport(
            sub_function=0x02,
            dtcs=[
                DTC(code=0xC07300, status=DTCStatus(0x2F)),
                DTC(code=0x010000, status=DTCStatus(0x04)),
                DTC(code=0x020000, status=DTCStatus(0x00)),
            ]
        )
        assert widget.set_report(report) == 3
        assert widget.counts() == {"confirmed": 1, "pending": 1, "warning": 0, "clean": 1}

    def test_table_selection_signal(self, qtbot, scaler) -> None:
        """Selecting a row publishes the matching DTC."""
        from ui.panels.diagnostic_panel.read_dtc_panel import DTCTableView

        widget = DTCTableView(scaler=scaler)
        qtbot.addWidget(widget)
        widget.set_dtcs([DTC(code=0xC07300, status=DTCStatus(0x08))])
        with qtbot.waitSignal(widget.dtc_selected, timeout=1000) as blocker:
            widget.selectRow(0)
        assert blocker.args[0].code == 0xC07300

    def test_detail_view_fills_the_identity_form(self, qtbot, scaler) -> None:
        """Every identity row is populated from the code."""
        from ui.panels.diagnostic_panel.read_dtc_panel import DTCDetailView

        widget = DTCDetailView(scaler=scaler)
        qtbot.addWidget(widget)
        widget.set_dtc(
            DTC(
                code=0xC07300,
                status=DTCStatus(0x2F),
                name="Left sensor",
                extended_records=[DTCExtendedRecord(1, b"\x05")],
            )
        )
        assert widget.fields["Code"].text() == "C0730"
        assert widget.fields["Category"].text() == "Network"
        assert widget.snapshot_button.isEnabled()

    def test_detail_view_emits_read_requests(self, qtbot, scaler) -> None:
        """The two read buttons publish the displayed code."""
        from ui.panels.diagnostic_panel.read_dtc_panel import DTCDetailView

        widget = DTCDetailView(scaler=scaler)
        qtbot.addWidget(widget)
        widget.set_dtc(DTC(code=0x010000, status=DTCStatus(0x08)))
        with qtbot.waitSignal(widget.snapshot_requested, timeout=1000) as blocker:
            widget.snapshot_button.click()
        assert blocker.args == [0x010000]

    def test_freeze_frame_decodes_the_identifiers(self, qtbot, scaler) -> None:
        """A snapshot record is decoded into its identifiers."""
        from ui.panels.diagnostic_panel.read_dtc_panel import DTCFreezeFrameView

        registry = DIDRegistry()
        registry.add(DIDDefinition(0xF190, "VIN", length=3))
        widget = DTCFreezeFrameView(scaler=scaler, registry=registry)
        qtbot.addWidget(widget)
        assert widget.set_records([DTCSnapshotRecord(1, bytes.fromhex("F190574241"))]) == 1
        items = widget.decoded_items()
        assert items[0]["did"] == 0xF190
        assert items[0]["ascii"] == "WBA"


# -- clear DTC ---------------------------------------------------------------
class TestClearDTCWidgets:
    """The group selector and the confirmation dialog."""

    def test_group_selector_masks(self, qtbot, scaler) -> None:
        """Each group maps to its ISO mask."""
        from ui.panels.diagnostic_panel.clear_dtc_panel import DTCGroupSelector

        widget = DTCGroupSelector(scaler=scaler)
        qtbot.addWidget(widget)
        assert widget.is_clear_all()
        assert widget.set_group("chassis")
        assert widget.mask() == 0x400000
        assert not widget.is_clear_all()

    def test_custom_mask_requires_three_bytes(self, qtbot, scaler) -> None:
        """The custom entry is invalid until three bytes are typed."""
        from ui.panels.diagnostic_panel.clear_dtc_panel import DTCGroupSelector

        widget = DTCGroupSelector(scaler=scaler)
        qtbot.addWidget(widget)
        widget.set_group("custom")
        assert not widget.is_valid()
        widget.custom_field.set_value(bytes.fromhex("C00000"))
        assert widget.is_valid()
        assert widget.mask() == 0xC00000

    def test_confirmation_requires_acknowledgement_for_clear_all(self, qtbot, scaler) -> None:
        """Clearing everything is gated behind the extra checkbox."""
        from ui.panels.diagnostic_panel.clear_dtc_panel import ClearConfirmationDialog

        dialog = ClearConfirmationDialog(0xFFFFFF, 3, scaler=scaler)
        qtbot.addWidget(dialog)
        assert not dialog.is_confirmed()
        dialog.acknowledge.setChecked(True)
        assert dialog.is_confirmed()

    def test_confirmation_is_immediate_for_a_group(self, qtbot, scaler) -> None:
        """A single group needs no second confirmation."""
        from ui.panels.diagnostic_panel.clear_dtc_panel import ClearConfirmationDialog

        dialog = ClearConfirmationDialog(0x400000, scaler=scaler)
        qtbot.addWidget(dialog)
        assert dialog.is_confirmed()


# -- security access ---------------------------------------------------------
class TestSecurityWidgets:
    """The level selector, the seed/key display and the algorithm source."""

    def test_level_selector_pairs_seed_and_key(self, qtbot, scaler) -> None:
        """Selecting level 0x03 implies sendKey 0x04."""
        from ui.panels.diagnostic_panel.security_access_panel import SecurityLevelSelector

        widget = SecurityLevelSelector(scaler=scaler)
        qtbot.addWidget(widget)
        widget.set_level(0x03)
        assert widget.level() == 0x03
        assert widget.key_level() == 0x04
        assert widget.is_valid()

    def test_seed_key_display_tracks_the_exchange(self, qtbot, scaler) -> None:
        """The summary follows the seed, the key and the result."""
        from ui.panels.diagnostic_panel.security_access_panel import SeedKeyDisplay

        widget = SeedKeyDisplay(scaler=scaler)
        qtbot.addWidget(widget)
        assert widget.summary() == "no seed requested yet"
        widget.begin_request(0x01)
        widget.set_seed(b"\x11\x22")
        widget.set_key(b"\xee\xdd", "xor_complement")
        widget.set_result(True, "unlocked")
        assert widget.unlocked
        assert widget.summary() == "seed 11 22 -> key EE DD (xor_complement)"

    def test_all_zero_seed_reports_unlocked(self, qtbot, scaler) -> None:
        """An all-zero seed short-circuits to the unlocked state."""
        from ui.panels.diagnostic_panel.security_access_panel import SeedKeyDisplay

        widget = SeedKeyDisplay(scaler=scaler)
        qtbot.addWidget(widget)
        widget.begin_request(0x01)
        widget.set_seed(b"\x00\x00\x00\x00")
        assert widget.unlocked

    def test_dll_config_shows_only_the_relevant_editors(self, qtbot, scaler) -> None:
        """The built-in source needs neither a file nor an entry point."""
        from src.diagnostics.services.security.security_dll_loader import AlgorithmSource
        from ui.panels.diagnostic_panel.security_access_panel import SecurityDLLConfig

        widget = SecurityDLLConfig(scaler=scaler)
        qtbot.addWidget(widget)
        assert widget.source() is AlgorithmSource.BUILTIN
        assert widget.is_ready()
        widget.set_source(AlgorithmSource.SHARED_LIBRARY)
        assert not widget.is_ready()
        assert widget.configuration()["source"] == "SHARED_LIBRARY"


# -- transfer ----------------------------------------------------------------
class TestTransferWidgets:
    """The firmware queue, the layout view, the progress and the log."""

    def test_queue_accepts_and_reorders_files(self, qtbot, scaler, tmp_path) -> None:
        """Files can be queued, moved and disabled."""
        from ui.panels.diagnostic_panel.transfer_panel import FileSelectorPanel

        first = tmp_path / "a.hex"
        second = tmp_path / "b.bin"
        first.write_text(":00000001FF\n")
        second.write_bytes(b"\x00" * 16)
        widget = FileSelectorPanel(scaler=scaler)
        qtbot.addWidget(widget)
        assert widget.add_paths([first, second]) == 2
        assert widget.add_path(first) is None
        widget.table.selectRow(1)
        assert widget.move_selected(-1)
        assert widget.files[0].path == second

    def test_queue_totals_only_enabled_files(self, qtbot, scaler, tmp_path) -> None:
        """Disabled entries do not contribute to the transfer size."""
        from ui.panels.diagnostic_panel.transfer_panel import FileSelectorPanel

        path = tmp_path / "a.bin"
        path.write_bytes(b"\x00" * 8)
        widget = FileSelectorPanel(scaler=scaler)
        qtbot.addWidget(widget)
        widget.add_path(path)
        widget.set_segments(path, [MemorySegment(0, b"\x00" * 8)])
        assert widget.total_size() == 8
        widget.files[0].enabled = False
        widget.refresh()
        assert widget.total_size() == 0

    def test_layout_view_reports_gaps(self, qtbot, scaler) -> None:
        """The summary counts the segments and the gaps between them."""
        from ui.panels.diagnostic_panel.transfer_panel import MemoryLayoutView

        widget = MemoryLayoutView(scaler=scaler)
        qtbot.addWidget(widget)
        widget.set_segments([MemorySegment(0, b"\x00" * 16), MemorySegment(0x100, b"\x00" * 16)])
        assert len(widget.gaps()) == 1
        assert "2 segment(s)" in widget.summary()

    def test_progress_view_tracks_the_transfer(self, qtbot, scaler) -> None:
        """The percentage, the blocks and the CRC are all displayed."""
        from src.core.enums.transfer_enums import TransferState
        from ui.panels.diagnostic_panel.transfer_panel import TransferProgressView

        widget = TransferProgressView(scaler=scaler)
        qtbot.addWidget(widget)
        widget.update_progress(
            TransferProgress(
                state=TransferState.TRANSFERRING,
                bytes_total=2048,
                bytes_done=1024,
                blocks_total=2,
                blocks_done=1,
                started_at=1.0,
                updated_at=2.0,
                message="Transferring data",
            )
        )
        assert widget.percent() == 50.0
        assert widget.blocks_label.text() == "1/2"
        widget.set_crc(0x9F5EDD58)
        assert widget.crc_label.full_text() == "0x9F5EDD58"

    def test_log_view_records_and_exports(self, qtbot, scaler, tmp_path) -> None:
        """Steps are logged in order and can be written to disk."""
        from ui.panels.diagnostic_panel.transfer_panel import TransferLogView

        widget = TransferLogView(scaler=scaler)
        qtbot.addWidget(widget)
        widget.start_session()
        widget.log("RequestDownload", "0x8000")
        widget.log("TransferData", "block 1", duration_ms=3.2)
        widget.log("Exit", "crc mismatch", "error")
        assert len(widget.entries) == 3
        assert widget.error_count() == 1
        target = widget.export_text(tmp_path / "log.txt")
        assert "RequestDownload" in target.read_text()


# -- developer mode ----------------------------------------------------------
class TestDeveloperWidgets:
    """The payload editor, the buttons, the mapper and the watch panel."""

    def test_payload_widget_composes_the_request(self, qtbot, scaler) -> None:
        """The SID is prefixed to the typed parameters."""
        from ui.panels.developer_panel import PayloadEntryWidget

        widget = PayloadEntryWidget(scaler=scaler, service_id=0x22)
        qtbot.addWidget(widget)
        widget.set_parameters("F190")
        assert widget.payload() == bytes.fromhex("22F190")
        assert widget.is_valid()

    def test_payload_widget_reports_a_short_payload(self, qtbot, scaler) -> None:
        """A one byte identifier is not enough for 0x22."""
        from ui.panels.developer_panel import PayloadEntryWidget

        widget = PayloadEntryWidget(scaler=scaler, service_id=0x22)
        qtbot.addWidget(widget)
        widget.set_parameters("F1")
        assert not widget.is_valid()

    def test_payload_widget_loads_a_full_request(self, qtbot, scaler) -> None:
        """Setting a whole request switches the service too."""
        from ui.panels.developer_panel import PayloadEntryWidget

        widget = PayloadEntryWidget(scaler=scaler, service_id=0x22)
        qtbot.addWidget(widget)
        widget.set_payload(bytes.fromhex("1003"))
        assert widget.service_id == 0x10
        assert widget.parameters() == b"\x03"

    def test_run_button_reflects_the_result(self, qtbot, scaler) -> None:
        """Running then finishing clears the spinner."""
        from ui.panels.developer_panel import RunButtonWidget

        step = TestStep(0x22, "Read DID")
        widget = RunButtonWidget(step, scaler=scaler)
        qtbot.addWidget(widget)
        widget.set_running(True)
        assert widget.running
        widget.apply_result(TestResult(step, TestStatus.PASS))
        assert not widget.running

    def test_run_button_emits_the_step(self, qtbot, scaler) -> None:
        """Clicking publishes the bound step."""
        from ui.panels.developer_panel import RunButtonWidget

        step = TestStep(0x22, "Read DID")
        widget = RunButtonWidget(step, scaler=scaler)
        qtbot.addWidget(widget)
        with qtbot.waitSignal(widget.run_requested, timeout=1000) as blocker:
            widget.click()
        assert blocker.args[0] is step

    def test_run_all_button_summarises(self, qtbot, scaler) -> None:
        """The caption shows the step count and then the summary."""
        from ui.panels.developer_panel import RunAllButton

        step = TestStep(0x22, "Read DID")
        widget = RunAllButton(scaler=scaler)
        qtbot.addWidget(widget)
        widget.set_sequence(TestSequence(steps=[step]))
        assert "1" in widget.text()
        widget.start()
        summary = widget.finish(
            [TestResult(step, TestStatus.PASS), TestResult(step, TestStatus.FAIL)]
        )
        assert summary == "1 passed, 1 failed"

    def test_cancel_button_arms_the_watchdog(self, qtbot, scaler) -> None:
        """Cancelling warns when the runner does not stop in time."""
        from ui.panels.developer_panel import CancelButton

        widget = CancelButton(scaler=scaler, timeout_ms=20)
        qtbot.addWidget(widget)
        assert not widget.isEnabled()
        widget.set_running(True)
        with qtbot.waitSignal(widget.cancel_timed_out, timeout=1000):
            assert widget.request_cancel()
        widget.acknowledge()
        assert not widget.is_cancelling()

    def test_script_editor_validates_the_template(self, qtbot, scaler) -> None:
        """A freshly generated template is valid."""
        from ui.panels.developer_panel import ScriptEditorPanel

        widget = ScriptEditorPanel(scaler=scaler)
        qtbot.addWidget(widget)
        widget.new_script(0x22, "Read DID")
        assert widget.validate().valid
        assert widget.is_valid()

    def test_script_editor_round_trips_a_file(self, qtbot, scaler, tmp_path) -> None:
        """Saving then loading preserves the source."""
        from ui.panels.developer_panel import ScriptEditorPanel

        widget = ScriptEditorPanel(scaler=scaler)
        qtbot.addWidget(widget)
        widget.new_script(0x10)
        target = widget.save(tmp_path / "script.py")
        widget.set_source("")
        widget.load(target)
        assert "class TestScript" in widget.source()

    def test_mapper_applies_to_a_sequence(self, qtbot, scaler) -> None:
        """Attaching a script updates the matching step."""
        from src.core.models.test_sequence_model import ExecutionMode
        from ui.panels.developer_panel import TestFileMapper

        widget = TestFileMapper(scaler=scaler)
        qtbot.addWidget(widget)
        widget.assign(0x10, "/tmp/session.py", "Session")
        sequence = TestSequence(steps=[TestStep(0x10, "Session")])
        assert widget.apply_to_sequence(sequence) == 1
        assert sequence.steps[0].script_path == "/tmp/session.py"
        assert sequence.steps[0].mode is ExecutionMode.SCRIPT

    def test_watch_panel_records_history(self, qtbot, scaler) -> None:
        """Repeated identical values are not recorded twice."""
        from ui.panels.developer_panel import VariableWatchPanel

        widget = VariableWatchPanel(scaler=scaler)
        qtbot.addWidget(widget)
        widget.set_auto_refresh(False)
        assert widget.set_variable("vin", "WBA")
        assert not widget.set_variable("vin", "WBA")
        assert widget.set_variable("vin", "BMW")
        assert widget.get("vin") == "BMW"
        assert widget.history("vin") == ["WBA", "BMW"]


# -- log panel ---------------------------------------------------------------
class TestLogPanelWidgets:
    """The filter editor, the search bar and the export dialog."""

    def test_filter_panel_round_trips(self, qtbot, scaler) -> None:
        """A filter loaded into the editors is rebuilt unchanged."""
        from src.logging_system.log_filter import LogFilter
        from ui.panels.log_panel import LogFilterPanel

        widget = LogFilterPanel(scaler=scaler)
        qtbot.addWidget(widget)
        original = LogFilter(
            min_level=LogLevel.WARNING,
            directions={"TX"},
            id_from=0x700,
            id_to=0x7FF,
            contains="7E8",
            hide_tester_present=True,
        )
        widget.apply_filter(original)
        rebuilt = widget.build_filter()
        assert rebuilt.min_level is LogLevel.WARNING
        assert rebuilt.directions == {"TX"}
        assert (rebuilt.id_from, rebuilt.id_to) == (0x700, 0x7FF)
        assert rebuilt.hide_tester_present

    def test_filter_panel_reset(self, qtbot, scaler) -> None:
        """Resetting clears every criterion."""
        from src.logging_system.log_filter import LogFilter
        from ui.panels.log_panel import LogFilterPanel

        widget = LogFilterPanel(scaler=scaler)
        qtbot.addWidget(widget)
        widget.apply_filter(LogFilter(min_level=LogLevel.ERROR))
        widget.reset()
        assert not widget.build_filter().is_active()

    def test_filter_panel_saves_to_yaml(self, qtbot, scaler, tmp_path) -> None:
        """A saved filter reloads with the same severity."""
        from src.logging_system.log_filter import LogFilter
        from ui.panels.log_panel import LogFilterPanel

        widget = LogFilterPanel(scaler=scaler)
        qtbot.addWidget(widget)
        widget.apply_filter(LogFilter(min_level=LogLevel.ERROR))
        target = widget.save(tmp_path / "filter.yaml")
        widget.reset()
        assert widget.load(target).min_level is LogLevel.ERROR

    def test_search_panel_navigates_the_matches(self, qtbot, scaler) -> None:
        """Next and previous cycle through the matching rows."""
        from ui.panels.log_panel import LogSearchPanel

        widget = LogSearchPanel(scaler=scaler, debounce_ms=0)
        qtbot.addWidget(widget)
        widget.set_entries(
            [LogEntry(message="alpha"), LogEntry(message="beta"), LogEntry(message="alpha two")]
        )
        widget.field.setText("alpha")
        assert widget.search() == [0, 2]
        assert widget.find_next() == 2
        assert widget.find_next() == 0
        assert widget.find_previous() == 2

    def test_search_panel_reports_no_match(self, qtbot, scaler) -> None:
        """A needle without a match is reported in the status label."""
        from ui.panels.log_panel import LogSearchPanel

        widget = LogSearchPanel(scaler=scaler, debounce_ms=0)
        qtbot.addWidget(widget)
        widget.set_entries([LogEntry(message="alpha")])
        widget.field.setText("zzz")
        widget.search()
        assert widget.match_count() == 0
        assert widget.status_label.text() == "no match"

    def test_export_dialog_writes_the_selected_scope(self, qtbot, scaler, tmp_path) -> None:
        """Only the filtered entries are written by default."""
        from ui.panels.log_panel import LogExportDialog

        entries = [LogEntry(message=f"entry {i}") for i in range(5)]
        dialog = LogExportDialog(entries, entries[:2], scaler=scaler)
        qtbot.addWidget(dialog)
        assert len(dialog.selected_entries()) == 2
        target = dialog.run_export(tmp_path / "log.csv")
        assert target is not None
        assert len(target.read_text().splitlines()) == 3


# -- data plot ---------------------------------------------------------------
class TestDataPlotPanel:
    """The painted time series chart."""

    def test_series_are_created_on_demand(self, qtbot, scaler) -> None:
        """Appending to an unknown name creates the series."""
        from ui.panels.data_analysis_panel import DataPlotPanel

        widget = DataPlotPanel(scaler=scaler)
        qtbot.addWidget(widget)
        widget.append("rpm", 800.0)
        widget.append("rpm", 900.0)
        assert list(widget.series) == ["rpm"]
        assert widget.series["rpm"].latest() == 900.0

    def test_pause_freezes_the_chart(self, qtbot, scaler) -> None:
        """No sample is recorded while the chart is paused."""
        from ui.panels.data_analysis_panel import DataPlotPanel

        widget = DataPlotPanel(scaler=scaler)
        qtbot.addWidget(widget)
        widget.append("rpm", 800.0)
        widget.toggle_pause()
        widget.append("rpm", 900.0)
        assert len(widget.series["rpm"]) == 1

    def test_append_values_uses_the_numeric_reading(self, qtbot, scaler) -> None:
        """Byte payloads are converted into a big-endian integer."""
        from ui.panels.data_analysis_panel import DataPlotPanel

        widget = DataPlotPanel(scaler=scaler)
        qtbot.addWidget(widget)
        definition = DIDDefinition(0xF1A0, "temp", unit="C")
        assert widget.append_values([DIDValue(did=0xF1A0, raw=b"\x01\x2c", definition=definition)]) == 1
        assert widget.series["temp"].latest() == 300.0

    def test_canvas_paints_without_error(self, qtbot, scaler) -> None:
        """Rendering a populated chart does not raise."""
        from ui.panels.data_analysis_panel import DataPlotPanel

        widget = DataPlotPanel(scaler=scaler)
        qtbot.addWidget(widget)
        for index in range(200):
            widget.append("rpm", 800.0 + index)
        widget.canvas.resize(400, 200)
        assert not widget.canvas.grab().isNull()


# -- settings pages ----------------------------------------------------------
class TestSettingsPages:
    """The five settings pages."""

    def test_general_page_binds_every_spec(self, qtbot, scaler) -> None:
        """One editor exists per declared setting."""
        from ui.panels.settings_panel import GeneralSettingsPage
        from ui.panels.settings_panel.general_settings import SETTINGS

        page = GeneralSettingsPage(scaler=scaler)
        qtbot.addWidget(page)
        assert set(page.paths()) == {spec.path for spec in SETTINGS}
        assert len(page.values()) == len(SETTINGS)

    def test_protocol_page_exposes_the_isotp_timing(self, qtbot, scaler) -> None:
        """The ISO-TP block size and STmin are editable."""
        from ui.panels.settings_panel import ProtocolSettingsPage

        page = ProtocolSettingsPage(scaler=scaler)
        qtbot.addWidget(page)
        assert "protocols.isotp.block_size" in page.values()
        assert "protocols.isotp.st_min_ms" in page.values()

    def test_display_page_preview(self, qtbot, scaler) -> None:
        """The preview follows the selected theme."""
        from ui.panels.settings_panel import DisplaySettingsPage

        page = DisplaySettingsPage(scaler=scaler)
        qtbot.addWidget(page)
        page.editors["ui.theme"].setCurrentText("light")
        assert "#F8FAFC" in page.preview()

    def test_logging_page_disk_estimate(self, qtbot, scaler) -> None:
        """The estimate reacts to the rotation settings."""
        from ui.panels.settings_panel import LoggingSettingsPage

        page = LoggingSettingsPage(scaler=scaler)
        qtbot.addWidget(page)
        page.editors["logging.max_file_size_mb"].setValue(10)
        page.editors["logging.backup_count"].setValue(4)
        assert page.disk_usage().startswith("50 MB")

    def test_plugin_page_lists_the_manager(self, qtbot, scaler) -> None:
        """Discovered plugins appear in the table."""
        from src.core.plugin_manager import PluginManager
        from ui.panels.settings_panel import PluginSettingsPage

        manager = PluginManager()
        manager.discover_and_load()
        page = PluginSettingsPage(scaler=scaler, manager=manager)
        qtbot.addWidget(page)
        assert page.table.rowCount() == len(manager.describe())

    def test_page_reload_restores_the_configuration(self, qtbot, scaler) -> None:
        """Editing then reloading discards the change."""
        from ui.panels.settings_panel import GeneralSettingsPage

        page = GeneralSettingsPage(scaler=scaler)
        qtbot.addWidget(page)
        editor = page.editors["paths.exports"]
        original = editor.text()
        editor.setText("/tmp/changed")
        page.reload()
        assert editor.text() == original


# -- dialogs -----------------------------------------------------------------
class TestDialogs:
    """The five remaining application dialogs."""

    def test_preferences_collects_every_page(self, qtbot, scaler) -> None:
        """The dialog aggregates the values of all five pages."""
        from ui.dialogs import PreferencesDialog

        dialog = PreferencesDialog(scaler=scaler)
        qtbot.addWidget(dialog)
        assert len(dialog.pages) == 5
        assert dialog.show_page("Logging")
        assert not dialog.show_page("Nope")
        assert dialog.pending_changes() == []

    def test_preferences_detects_a_change(self, qtbot, scaler) -> None:
        """Editing a field is reported as a pending change."""
        from ui.dialogs import PreferencesDialog

        dialog = PreferencesDialog(scaler=scaler)
        qtbot.addWidget(dialog)
        dialog.pages["General"].editors["paths.exports"].setText("/tmp/vdp-exports")
        assert "paths.exports" in dialog.pending_changes()

    def test_vci_dialog_builds_a_profile(self, qtbot, scaler) -> None:
        """The editors produce a usable connection profile."""
        from ui.dialogs import VCIConfigDialog

        dialog = VCIConfigDialog(scaler=scaler)
        qtbot.addWidget(dialog)
        profile = dialog.profile()
        assert profile.tx_id == 0x7E0
        assert profile.rx_id == 0x7E8
        assert dialog.is_valid()

    def test_vci_dialog_round_trips_a_profile(self, qtbot, scaler, tmp_path) -> None:
        """A saved profile reloads with the same identifiers."""
        from src.communication.connection_manager import ConnectionProfile
        from ui.dialogs import VCIConfigDialog

        dialog = VCIConfigDialog(scaler=scaler)
        qtbot.addWidget(dialog)
        dialog.set_profile(ConnectionProfile(tx_id=0x7A0, rx_id=0x7A8, bitrate=250_000))
        target = dialog.save(tmp_path / "profile.yaml")
        reloaded = dialog.load(target)
        assert (reloaded.tx_id, reloaded.rx_id, reloaded.bitrate) == (0x7A0, 0x7A8, 250_000)

    def test_transfer_dialog_parses_the_firmware(self, qtbot, scaler, tmp_path) -> None:
        """Selecting a binary pre-fills the address and the size."""
        from ui.dialogs import FileTransferDialog

        firmware = tmp_path / "fw.bin"
        firmware.write_bytes(b"\xaa" * 2048)
        dialog = FileTransferDialog(scaler=scaler, path=str(firmware))
        qtbot.addWidget(dialog)
        request = dialog.request()
        assert request["size"] == 2048
        assert dialog.is_valid()

    def test_transfer_dialog_emits_the_request(self, qtbot, scaler, tmp_path) -> None:
        """Starting publishes the assembled request mapping."""
        from ui.dialogs import FileTransferDialog

        firmware = tmp_path / "fw.bin"
        firmware.write_bytes(b"\xaa" * 1024)
        dialog = FileTransferDialog(scaler=scaler, path=str(firmware))
        qtbot.addWidget(dialog)
        with qtbot.waitSignal(dialog.transfer_requested, timeout=1000) as blocker:
            dialog.start()
        assert blocker.args[0]["size"] == 1024
        dialog.finish(True, "done", crc=0x12345678)
        assert dialog.progress_view.crc_label.full_text() == "0x12345678"

    def test_identification_dialog_decodes_the_vin(self, qtbot, scaler) -> None:
        """The VIN summary is filled from the ECU identification."""
        from ui.dialogs import ECUIdentificationDialog

        ecu = ECU(name="ECM", identification=ECUIdentification(vin="WBAZZZ0GM12345678"))
        dialog = ECUIdentificationDialog(scaler=scaler, ecu=ecu)
        qtbot.addWidget(dialog)
        assert dialog.vin() == "WBAZZZ0GM12345678"
        assert dialog.wmi_label.text() == "WBA"

    def test_identification_dialog_fills_from_readings(self, qtbot, scaler) -> None:
        """Reading the identifiers populates the table and the VIN."""
        from ui.dialogs import ECUIdentificationDialog

        dialog = ECUIdentificationDialog(scaler=scaler)
        qtbot.addWidget(dialog)
        dialog.set_values(
            [
                DIDValue(did=0xF190, raw=b"WBAZZZ0GM12345678"),
                DIDValue(did=0xF18C, raw=b"SN-0001"),
            ]
        )
        assert dialog.table.rowCount() == 2
        assert dialog.vin() == "WBAZZZ0GM12345678"

    def test_identification_dialog_requests_the_dids(self, qtbot, scaler) -> None:
        """Pressing Read publishes the identifier list."""
        from ui.dialogs import ECUIdentificationDialog

        dialog = ECUIdentificationDialog(scaler=scaler)
        qtbot.addWidget(dialog)
        with qtbot.waitSignal(dialog.read_requested, timeout=1000) as blocker:
            dialog.read_button.click()
        assert 0xF190 in blocker.args[0]

    def test_report_dialog_renders_every_format(self, qtbot, scaler) -> None:
        """Switching the format changes the preview."""
        from ui.dialogs import ReportData, ReportGeneratorDialog

        data = ReportData(
            title="Session",
            dtcs=[DTC(code=0xC07300, status=DTCStatus(0x2F), name="Sensor")],
        )
        dialog = ReportGeneratorDialog(data, scaler=scaler)
        qtbot.addWidget(dialog)
        for name, marker in (("HTML", "<!DOCTYPE html>"), ("Markdown", "# Session")):
            dialog.format_box.setCurrentText(name)
            assert dialog.render().startswith(marker)

    def test_report_dialog_saves(self, qtbot, scaler, tmp_path) -> None:
        """The rendered report is written to disk."""
        from ui.dialogs import ReportData, ReportGeneratorDialog

        dialog = ReportGeneratorDialog(ReportData(title="S"), scaler=scaler)
        qtbot.addWidget(dialog)
        with qtbot.waitSignal(dialog.report_saved, timeout=1000):
            target = dialog.save(tmp_path / "report.html")
        assert target.exists()
        assert "S" in target.read_text()


# -- service tab manager with a real tab widget ------------------------------
class TestServiceTabManagerWithWidget:
    """The manager driving a real :class:`EnhancedTabWidget`."""

    def test_tabs_follow_the_connection_state(self, qtbot, scaler) -> None:
        """Tabs are disabled while disconnected and enabled afterwards."""
        from ui.panels.diagnostic_panel import ServiceTabManager
        from ui.widgets.tab_widget_enhanced import EnhancedTabWidget
        from PySide6.QtWidgets import QWidget

        tabs = EnhancedTabWidget(scaler=scaler)
        qtbot.addWidget(tabs)
        titles = ["Session", "Read DID", "Security"]
        for title in titles:
            tabs.add_panel(QWidget(), title)
        manager = ServiceTabManager(tabs, titles)
        manager.set_connected(False)
        assert not tabs.isTabEnabled(0)
        manager.set_connected(True)
        assert tabs.isTabEnabled(0)

    def test_states_changed_signal(self, qtbot, scaler) -> None:
        """Every refresh publishes the full state mapping."""
        from ui.panels.diagnostic_panel import ServiceTabManager

        manager = ServiceTabManager(titles=["Session", "Security"])
        with qtbot.waitSignal(manager.states_changed, timeout=1000) as blocker:
            manager.set_connected(True)
        assert set(blocker.args[0]) == {"Session", "Security"}


class TestCodeGeneratorPanel:
    """The developer mode Code Generator."""

    def test_builds_a_valid_script_from_the_form(self, qtbot, scaler) -> None:
        """Adding steps produces a script the validator accepts."""
        import ast

        from src.test_execution.code_generator import STEP_KINDS
        from ui.panels.developer_panel import CodeGeneratorPanel

        panel = CodeGeneratorPanel(scaler=scaler)
        qtbot.addWidget(panel)
        panel.name_field.setText("Entry check")
        kinds = [kind for kind, _ in STEP_KINDS]
        panel.kind_box.setCurrentIndex(kinds.index("read_did"))
        panel.add_step()
        panel.kind_box.setCurrentIndex(kinds.index("read_dtc"))
        panel.add_step()
        assert len(panel.steps) == 2
        source = panel.generated_code()
        assert ast.parse(source) is not None
        assert "class TestScript" in source

    def test_step_reordering(self, qtbot, scaler) -> None:
        """Steps can be moved and removed."""
        from src.test_execution.code_generator import STEP_KINDS
        from ui.panels.developer_panel import CodeGeneratorPanel

        panel = CodeGeneratorPanel(scaler=scaler)
        qtbot.addWidget(panel)
        kinds = [kind for kind, _ in STEP_KINDS]
        panel.kind_box.setCurrentIndex(kinds.index("session"))
        panel.add_step()
        panel.kind_box.setCurrentIndex(kinds.index("read_did"))
        panel.add_step()
        first = panel.steps[0].kind
        panel.step_list.setCurrentRow(0)
        assert panel.move_selected(1)
        assert panel.steps[1].kind == first
        panel.step_list.setCurrentRow(0)
        assert panel.remove_selected()
        assert len(panel.steps) == 1

    def test_yaml_output_switch(self, qtbot, scaler) -> None:
        """The panel can emit a developer mode sequence instead of Python."""
        from ui.panels.developer_panel import CodeGeneratorPanel

        panel = CodeGeneratorPanel(scaler=scaler)
        qtbot.addWidget(panel)
        panel.add_step()
        panel.format_box.setCurrentIndex(1)
        assert panel.generated_code().startswith("test_sequence:")

    def test_template_prefills_steps(self, qtbot, scaler) -> None:
        """Choosing a reference template seeds the step list."""
        from ui.panels.developer_panel import CodeGeneratorPanel

        panel = CodeGeneratorPanel(scaler=scaler)
        qtbot.addWidget(panel)
        index = panel.template_box.findData("clear_dtc_template.py")
        assert index >= 0
        panel.template_box.setCurrentIndex(index)
        assert len(panel.steps) == 3

    def test_saves_to_disk(self, qtbot, scaler, tmp_path) -> None:
        """The generated script is written and announced."""
        from ui.panels.developer_panel import CodeGeneratorPanel

        panel = CodeGeneratorPanel(scaler=scaler)
        qtbot.addWidget(panel)
        panel.add_step()
        with qtbot.waitSignal(panel.script_generated, timeout=1000):
            target = panel.save(tmp_path / "generated.py")
        assert target.exists()
        assert "TestScript" in target.read_text()

    def test_developer_panel_exposes_the_generator_tab(self, qtbot, scaler) -> None:
        """The generator is reachable from developer mode."""
        from ui.panels.developer_panel import DeveloperModePanel

        panel = DeveloperModePanel(scaler=scaler)
        qtbot.addWidget(panel)
        titles = [panel.tabs.tabText(i) for i in range(panel.tabs.count())]
        assert "Code generator" in titles
        assert "Script editor" in titles
        assert panel.tabs.select_by_title("Code generator")

    def test_send_to_editor_transfers_the_source(self, qtbot, scaler) -> None:
        """The generated code lands in the editor tab, ready to run."""
        from ui.panels.developer_panel import DeveloperModePanel

        panel = DeveloperModePanel(scaler=scaler)
        qtbot.addWidget(panel)
        panel.code_generator.add_step()
        panel._send_to_editor()
        assert "class TestScript" in panel.script_editor.source()
        assert panel.script_editor.validate().valid


class TestFlashSequenceEditor:
    """Drag and drop editing of the flashing sequence."""

    def test_default_sequence_is_listed(self, qtbot, scaler) -> None:
        """The 13 specification steps appear in the list."""
        from ui.panels.diagnostic_panel.transfer_panel import FlashSequenceEditor

        editor = FlashSequenceEditor(scaler=scaler)
        qtbot.addWidget(editor)
        assert len(editor.sequence) == 13
        assert editor.step_list.count() == 13

    def test_palette_groups_are_populated(self, qtbot, scaler) -> None:
        """Every category offers at least one draggable step."""
        from ui.panels.diagnostic_panel.transfer_panel import FlashSequenceEditor

        editor = FlashSequenceEditor(scaler=scaler)
        qtbot.addWidget(editor)
        assert editor.palette_tree.topLevelItemCount() >= 5
        for index in range(editor.palette_tree.topLevelItemCount()):
            assert editor.palette_tree.topLevelItem(index).childCount() > 0

    def test_dropping_a_palette_step_inserts_it(self, qtbot, scaler) -> None:
        """A step dragged in from the palette lands at the drop row."""
        from src.diagnostics.flash_sequence import FlashStepKind
        from ui.panels.diagnostic_panel.transfer_panel import FlashSequenceEditor

        editor = FlashSequenceEditor(scaler=scaler)
        qtbot.addWidget(editor)
        editor._on_step_dropped(FlashStepKind.TESTER_PRESENT, 2)
        assert editor.sequence.steps[2].kind is FlashStepKind.TESTER_PRESENT
        assert editor.step_list.count() == 14

    def test_internal_drag_reorders(self, qtbot, scaler) -> None:
        """Dragging inside the list changes the order."""
        from src.diagnostics.flash_sequence import FlashStepKind
        from ui.panels.diagnostic_panel.transfer_panel import FlashSequenceEditor

        editor = FlashSequenceEditor(scaler=scaler)
        qtbot.addWidget(editor)
        editor._on_step_moved(0, 4)
        assert editor.sequence.steps[4].kind is FlashStepKind.CAN_INIT

    def test_toggle_and_remove(self, qtbot, scaler) -> None:
        """A step can be disabled and deleted from the list."""
        from ui.panels.diagnostic_panel.transfer_panel import FlashSequenceEditor

        editor = FlashSequenceEditor(scaler=scaler)
        qtbot.addWidget(editor)
        editor.step_list.setCurrentRow(0)
        assert editor.toggle_selected() is False
        assert editor.sequence.steps[0].enabled is False
        assert editor.remove_selected()
        assert len(editor.sequence) == 12

    def test_start_is_gated_on_validation(self, qtbot, scaler, tmp_path) -> None:
        """Start flash stays disabled until a flash file is chosen."""
        from ui.panels.diagnostic_panel.transfer_panel import FlashSequenceEditor

        editor = FlashSequenceEditor(scaler=scaler)
        qtbot.addWidget(editor)
        assert not editor.start_button.isEnabled()
        firmware = tmp_path / "fw.bin"
        firmware.write_bytes(b"\xaa" * 256)
        editor.flash_file.set_path(firmware)
        assert editor.start_button.isEnabled()

    def test_bad_order_disables_start(self, qtbot, scaler, tmp_path) -> None:
        """An impossible order is reported and blocks the run."""
        from src.diagnostics.flash_sequence import FlashStepKind
        from ui.panels.diagnostic_panel.transfer_panel import FlashSequenceEditor

        editor = FlashSequenceEditor(scaler=scaler)
        qtbot.addWidget(editor)
        firmware = tmp_path / "fw.bin"
        firmware.write_bytes(b"\xaa" * 256)
        editor.flash_file.set_path(firmware)
        download = next(
            i
            for i, s in enumerate(editor.sequence.steps)
            if s.kind is FlashStepKind.REQUEST_DOWNLOAD
        )
        editor._on_step_moved(download, download + 1)
        assert not editor.start_button.isEnabled()
        assert "must run before" in editor.status_label.text()

    def test_sequence_round_trips_through_yaml(self, qtbot, scaler, tmp_path) -> None:
        """A saved sequence reloads with the same steps."""
        from src.diagnostics.flash_sequence import FlashStepKind
        from ui.panels.diagnostic_panel.transfer_panel import FlashSequenceEditor

        editor = FlashSequenceEditor(scaler=scaler)
        qtbot.addWidget(editor)
        editor._on_step_dropped(FlashStepKind.DELAY, 0)
        target = editor.save(tmp_path / "sequence.yaml")
        editor.restore_default()
        assert len(editor.sequence) == 13
        editor.load(target)
        assert editor.sequence.steps[0].kind is FlashStepKind.DELAY


class TestFlashProgressView:
    """The live flashing screen."""

    def test_stage_bars_exist(self, qtbot, scaler) -> None:
        """One bar per stage, as in the reference tester."""
        from ui.panels.diagnostic_panel.transfer_panel.flash_progress_view import (
            STAGES,
            FlashProgressView,
        )

        view = FlashProgressView(scaler=scaler)
        qtbot.addWidget(view)
        assert set(view.stage_bars) == set(STAGES)

    def test_progress_updates_the_transfer_block(self, qtbot, scaler) -> None:
        """Blocks, bytes and percentage are all shown."""
        from src.core.enums.transfer_enums import TransferState
        from src.core.models.file_transfer_model import TransferProgress
        from ui.panels.diagnostic_panel.transfer_panel.flash_progress_view import (
            FlashProgressView,
        )

        view = FlashProgressView(scaler=scaler)
        qtbot.addWidget(view)
        view.update_progress(
            TransferProgress(
                state=TransferState.TRANSFERRING,
                bytes_total=4096,
                bytes_done=1024,
                blocks_total=4,
                blocks_done=1,
                started_at=1.0,
                updated_at=2.0,
            )
        )
        assert view.transfer_bar.value() == 25
        assert view.blocks_label.text() == "1/4"

    def test_step_outcome_fills_the_log_and_card(self, qtbot, scaler) -> None:
        """A finished step appends a log row and populates the ECU card."""
        from src.diagnostics.flash_sequence import (
            FlashSequence,
            FlashStep,
            FlashStepKind,
            StepOutcome,
            StepStatus,
        )
        from ui.panels.diagnostic_panel.transfer_panel.flash_progress_view import (
            FlashProgressView,
        )

        view = FlashProgressView(scaler=scaler)
        qtbot.addWidget(view)
        view.begin(FlashSequence.default())
        step = FlashStep(kind=FlashStepKind.READ_VIN)
        view.step_finished(
            StepOutcome(step, StepStatus.PASSED, "VIN WBAZZZ0GM12345678", 2.7,
                        {"vin": "WBAZZZ0GM12345678"})
        )
        assert view.log.rowCount() == 1
        assert view.fields["VIN"].full_text() == "WBAZZZ0GM12345678"

    def test_log_rows_render_their_text(self, qtbot, scaler) -> None:
        """Appended rows must actually show their cells.

        Sorting was re-ordering the table between cell writes, which left the
        transcript looking empty.
        """
        from src.diagnostics.flash_sequence import (
            FlashSequence,
            FlashStep,
            FlashStepKind,
            StepOutcome,
            StepStatus,
        )
        from ui.panels.diagnostic_panel.transfer_panel.flash_progress_view import (
            FlashProgressView,
        )

        view = FlashProgressView(scaler=scaler)
        qtbot.addWidget(view)
        view.begin(FlashSequence.default())
        for index in range(5):
            view.step_finished(
                StepOutcome(
                    FlashStep(kind=FlashStepKind.ECU_COMM),
                    StepStatus.PASSED,
                    f"detail {index}",
                    1.0,
                )
            )
        assert view.log.rowCount() == 5
        for row in range(5):
            assert view.log.item(row, 3) is not None
            assert view.log.item(row, 3).text() == f"detail {row}"

    def test_finish_marks_every_stage_complete(self, qtbot, scaler) -> None:
        """A successful run fills all the stage bars."""
        from src.diagnostics.flash_runner import FlashReport
        from src.diagnostics.flash_sequence import FlashSequence
        from ui.panels.diagnostic_panel.transfer_panel.flash_progress_view import (
            FlashProgressView,
        )

        view = FlashProgressView(scaler=scaler)
        qtbot.addWidget(view)
        view.begin(FlashSequence.default())
        view.finish(FlashReport())
        assert all(bar.value() == 100 for bar in view.stage_bars.values() if bar.isEnabled())


class TestFlashPanelWorkflow:
    """The two page panel driving a real run on a worker thread."""

    def test_start_switches_to_the_progress_page(self, qtbot, scaler, tmp_path) -> None:
        """Pressing start shows the live screen and completes the flash."""
        from intelhex import IntelHex

        from src.communication.vci_drivers.virtual.virtual_bus import VirtualBus
        from src.diagnostics.flash_sequence import FlashStep, FlashStepKind
        from tests.simulation.mock_ecu import make_simulator
        from tests.simulation.test_with_simulator import build_client, close
        from ui.panels.diagnostic_panel.transfer_panel import FlashPanel
        from ui.panels.diagnostic_panel.transfer_panel.flash_panel import (
            PAGE_EDITOR,
            PAGE_PROGRESS,
        )

        image = IntelHex()
        image.frombytes(bytes(range(256)) * 8, offset=0x08000000)
        firmware = tmp_path / "fw.hex"
        image.write_hex_file(str(firmware))

        bus = VirtualBus("ui-flash-test")
        client, driver, transport = build_client(make_simulator(bus), bus, 4000.0)
        try:
            panel = FlashPanel(scaler=scaler, client=client)
            qtbot.addWidget(panel)
            panel.editor.flash_file.set_path(firmware)
            index = next(
                i
                for i, s in enumerate(panel.editor.sequence.steps)
                if s.kind is FlashStepKind.SECURITY_ACCESS
            )
            panel.editor.sequence.steps.insert(
                index, FlashStep(kind=FlashStepKind.ENTER_PROGRAMMING)
            )
            panel.editor.reload()
            assert panel.stack.currentIndex() == PAGE_EDITOR

            with qtbot.waitSignal(panel.flash_finished, timeout=20000) as blocker:
                assert panel.start_flash()
                assert panel.stack.currentIndex() == PAGE_PROGRESS
            report = blocker.args[0]
            assert report.completed, [o.message for o in report.failed]
            assert panel.progress_view.transfer_bar.value() == 100
            assert panel.progress_view.log.rowCount() >= 13
        finally:
            close(driver, transport)

    def test_start_without_a_client_reports_it(self, qtbot, scaler, tmp_path) -> None:
        """Flashing with no connection explains itself instead of crashing."""
        from ui.panels.diagnostic_panel.transfer_panel import FlashPanel

        firmware = tmp_path / "fw.bin"
        firmware.write_bytes(b"\xaa" * 256)
        panel = FlashPanel(scaler=scaler)
        qtbot.addWidget(panel)
        panel.editor.flash_file.set_path(firmware)
        assert not panel.start_flash()

    def test_invalid_sequence_is_refused(self, qtbot, scaler) -> None:
        """A sequence without a file never starts."""
        from ui.panels.diagnostic_panel.transfer_panel import FlashPanel

        panel = FlashPanel(scaler=scaler)
        qtbot.addWidget(panel)
        assert not panel.start_flash()

    def test_panel_is_reachable_from_the_diagnostic_tabs(self, qtbot, scaler) -> None:
        """The flashing workflow has its own service view."""
        from ui.panels.diagnostic_panel import DiagnosticMainPanel

        panel = DiagnosticMainPanel(scaler=scaler)
        qtbot.addWidget(panel)
        assert "ECU flashing" in panel.views
        assert panel.show_view("ECU flashing")


class TestReadDIDResultsAppear:
    """Regression: a DID typed into the field must show its result."""

    def test_unlisted_did_is_appended(self, qtbot, scaler) -> None:
        """``show_values`` used to drop identifiers not already in the table.

        Reading a DID typed straight into the field never adds a row first, so
        the result disappeared and the page looked broken.
        """
        from src.core.models.did_model import DIDDefinition, DIDRegistry, DIDValue
        from ui.panels.diagnostic_panel.read_did_panel import ReadDIDView

        registry = DIDRegistry()
        registry.add(DIDDefinition(0xF190, "VIN", length=17))
        view = ReadDIDView(scaler=scaler, registry=registry)
        qtbot.addWidget(view)
        assert view.did_table.rowCount() == 0

        view.show_values(
            [DIDValue(did=0xF190, raw=b"WBAZZZ0GM12345678",
                      definition=registry.get(0xF190))]
        )
        assert view.did_table.rowCount() == 1
        assert view.did_table.item(0, 0).text() == "F190"
        assert view.did_table.item(0, 1).text() == "VIN"

    def test_repeat_read_updates_in_place(self, qtbot, scaler) -> None:
        """Reading the same DID twice must not duplicate the row."""
        from src.core.models.did_model import DIDValue
        from ui.panels.diagnostic_panel.read_did_panel import ReadDIDView

        view = ReadDIDView(scaler=scaler)
        qtbot.addWidget(view)
        view.show_values([DIDValue(did=0xF190, raw=b"AAA")])
        view.show_values([DIDValue(did=0xF190, raw=b"BBB")])
        assert view.did_table.rowCount() == 1
        assert "42 42 42" in view.did_table.item(0, 3).text()

    def test_several_dids_accumulate(self, qtbot, scaler) -> None:
        """Sequential single reads build up the list."""
        from src.core.models.did_model import DIDValue
        from ui.panels.diagnostic_panel.read_did_panel import ReadDIDView

        view = ReadDIDView(scaler=scaler)
        qtbot.addWidget(view)
        for did in (0xF190, 0xF18C, 0xF195):
            view.show_values([DIDValue(did=did, raw=b"X")])
        assert view.did_table.rowCount() == 3


class TestControllerThreadSafety:
    """Worker callbacks must reach the UI thread through queued connections."""

    def test_diagnostic_worker_uses_queued_connections(self) -> None:
        """Direct delivery started spinner timers on the worker thread."""
        import inspect

        from ui.controllers import diagnostic_controller

        source = inspect.getsource(diagnostic_controller.DiagnosticController._run)
        assert "QueuedConnection" in source

    def test_developer_relays_are_queued(self) -> None:
        """The runner callback hops to the UI thread before touching widgets."""
        import inspect

        from ui.controllers import developer_mode_controller

        source = inspect.getsource(developer_mode_controller.DeveloperModeController)
        assert "_relay_started" in source
        assert "QueuedConnection" in source

    def test_step_callback_does_not_touch_the_panel(self) -> None:
        """``_on_step`` may only re-emit; widget work belongs in the slots."""
        import inspect

        from ui.controllers.developer_mode_controller import DeveloperModeController

        source = inspect.getsource(DeveloperModeController._on_step)
        assert "self.panel" not in source
        assert "_relay_started" in source


class TestSimulatorIdentificationBlock:
    """The bundled simulator must answer the flash identification reads."""

    def test_supplier_dids_are_present(self) -> None:
        """A flash sequence reads F192..F195; they must not be missing."""
        from src.communication.vci_drivers.virtual.ecu_simulator import DEFAULT_SIMULATOR_CONFIG

        dids = DEFAULT_SIMULATOR_CONFIG["dids"]
        for did in ("F191", "F192", "F194", "F195"):
            assert did in dids, f"{did} missing from the default simulator"

    def test_erase_routines_are_present(self) -> None:
        """The default flash sequence runs routine 0xFF00."""
        from src.communication.vci_drivers.virtual.ecu_simulator import DEFAULT_SIMULATOR_CONFIG

        assert "FF00" in DEFAULT_SIMULATOR_CONFIG["routines"]
        assert "FF01" in DEFAULT_SIMULATOR_CONFIG["routines"]


class TestTwoLevelNavigation:
    """Sections are top tabs, never a second navigation surface.

    The application must expose exactly two navigation rows, both at the top:
    the workspace row and the section row of the active workspace.  These
    tests lock that contract down so a section can never be re-introduced as
    a sidebar row while it is also a tab.
    """

    def test_tab_levels_are_distinct(self, qtbot) -> None:
        """A primary bar and a sub bar advertise different ``navlevel``."""
        from ui.widgets.tab_widget_enhanced import EnhancedTabWidget

        primary = EnhancedTabWidget(level="primary")
        sub = EnhancedTabWidget(level="sub")
        qtbot.addWidget(primary)
        qtbot.addWidget(sub)
        assert primary.property("navlevel") == "primary"
        assert sub.property("navlevel") == "sub"
        assert primary.tabBar().property("navlevel") == "primary"
        assert sub.tabBar().property("navlevel") == "sub"

    def test_navigation_bars_are_not_reorderable(self, qtbot) -> None:
        """Navigation keeps its documented order; tabs are not draggable."""
        from ui.widgets.tab_widget_enhanced import EnhancedTabWidget

        tabs = EnhancedTabWidget(level="sub")
        qtbot.addWidget(tabs)
        assert not tabs.isMovable()

    def test_compact_mode_keeps_every_tab(self, qtbot) -> None:
        """Compact mode hides labels but never removes or disables a tab."""
        from PySide6.QtWidgets import QWidget

        from ui.widgets.tab_widget_enhanced import EnhancedTabWidget

        tabs = EnhancedTabWidget(level="sub")
        qtbot.addWidget(tabs)
        for name in ("Session", "Read DID", "Read DTC"):
            tabs.add_panel(QWidget(), name, "play")
        tabs.set_compact(True)
        assert tabs.count() == 3
        assert [tabs.tabText(i) for i in range(3)] == ["", "", ""]
        assert tabs.titles() == ["Session", "Read DID", "Read DTC"]
        tabs.set_compact(False)
        assert tabs.titles() == [tabs.tabText(i) for i in range(3)]

    def test_diagnostic_sections_are_tabs(self, qtbot) -> None:
        """Every diagnostic view is reachable through the section tab bar."""
        from ui.panels.diagnostic_panel.diagnostic_main_panel import DiagnosticMainPanel

        panel = DiagnosticMainPanel()
        qtbot.addWidget(panel)
        assert panel.tabs.count() == len(panel.views)
        assert panel.tabs.titles() == list(panel.views)
        for title in panel.views:
            assert panel.show_view(title)
            assert panel.current_view() is panel.views[title]

    def test_diagnostic_breadcrumb_tracks_tab(self, qtbot) -> None:
        """Selecting a section updates the breadcrumb path."""
        from ui.panels.diagnostic_panel.diagnostic_main_panel import DiagnosticMainPanel

        panel = DiagnosticMainPanel()
        qtbot.addWidget(panel)
        panel.show_view("Read DTC")
        assert panel.breadcrumb.text() == "Diagnostics \u203a Read DTC"
        assert panel.breadcrumb.segments == ["Diagnostics", "Read DTC"]

    def test_analysis_workspace_groups_tools(self, qtbot) -> None:
        """The slicer/converter pair, the monitor and the plot are sections."""
        from ui.panels.data_analysis_panel.data_analysis_workspace import DataAnalysisWorkspace

        workspace = DataAnalysisWorkspace()
        qtbot.addWidget(workspace)
        assert workspace.sections() == ["Slicer", "Monitor", "Plot"]
        workspace.set_data(bytes.fromhex("62F190"))
        assert workspace.slicer_panel.slicer.data() == bytes.fromhex("62F190")
        assert workspace.converter_panel.data() == bytes.fromhex("62F190")
        # Both historical tab names resolve to the combined section.
        assert workspace.show_view("Response slicer")
        assert workspace.tabs.current_title() == "Slicer"
        assert workspace.show_view("Converter")
        assert workspace.tabs.current_title() == "Slicer"

    def test_log_workspace_groups_views(self, qtbot) -> None:
        """Log viewer and trace viewer are sections of one workspace."""
        from ui.panels.log_panel.log_workspace import LogWorkspace

        workspace = LogWorkspace()
        qtbot.addWidget(workspace)
        assert workspace.sections() == ["Log viewer", "Trace viewer"]
        assert workspace.show_view("Trace viewer")
        assert workspace.tabs.current_title() == "Trace viewer"

    def test_breadcrumb_drops_empty_segments(self, qtbot) -> None:
        """A workspace without a section renders a single crumb."""
        from ui.widgets.breadcrumb_widget import BreadcrumbWidget

        crumb = BreadcrumbWidget()
        qtbot.addWidget(crumb)
        assert crumb.set_path("Connection", "") == "Connection"
        assert crumb.set_path("Logs", "Trace viewer") == "Logs \u203a Trace viewer"


class TestSlicerConverterTrace:
    """The Data analysis workspace pairs the slicer with the converter.

    The converter exists to expand whichever field the operator highlighted
    in the slicer, and the live trace has to stay visible underneath both so
    the traffic that produced the bytes never leaves the screen.
    """

    def test_slicer_and_converter_share_one_section(self, qtbot) -> None:
        """Both tools are visible at once, not behind separate tabs."""
        from ui.panels.data_analysis_panel.data_analysis_workspace import DataAnalysisWorkspace

        workspace = DataAnalysisWorkspace()
        qtbot.addWidget(workspace)
        assert workspace.slice_splitter.count() == 2
        assert workspace.views["Slicer"] is workspace.slice_splitter

    def test_selecting_a_slice_drives_the_converter(self, qtbot) -> None:
        """Only the highlighted field reaches the converter."""
        from ui.panels.data_analysis_panel.data_analysis_workspace import DataAnalysisWorkspace

        workspace = DataAnalysisWorkspace()
        qtbot.addWidget(workspace)
        workspace.set_data(bytes.fromhex("62F190574241315A5A5A313233343536"))
        assert workspace.converter_panel.source() == "converting: whole response"

        slicer = workspace.slicer_panel.slicer
        assert slicer.select_slice(1)
        definition = slicer.selected_slice()
        assert definition is not None
        # The DID slice is bytes 1..2 of the response.
        assert slicer.selected_bytes() == bytes.fromhex("F190")
        assert workspace.converter_panel.data() == bytes.fromhex("F190")
        assert definition.name in workspace.converter_panel.source()

    def test_live_trace_colours_by_outcome(self, qtbot) -> None:
        """Pending, negative and positive responses are visually distinct."""
        from ui.styles.semantic_colors import semantic
        from ui.widgets.live_trace_widget import LiveTraceWidget

        trace = LiveTraceWidget()
        qtbot.addWidget(trace)
        trace.add_frame("TX", bytes.fromhex("22F190"))
        pending = trace.add_frame("RX", bytes.fromhex("7F2278"))
        positive = trace.add_frame("RX", bytes.fromhex("62F19057"))
        negative = trace.add_frame("RX", bytes.fromhex("7F2E33"))

        assert pending is not None and pending.pending
        assert negative is not None and negative.is_negative
        assert trace._render(pending)["_c"] == semantic("warning")
        assert trace._render(negative)["_c"] == semantic("error")
        assert trace._render(positive)["_c"] == semantic("success")
        assert trace.table.rowCount() == 4

    def test_live_trace_reports_round_trip_time(self, qtbot) -> None:
        """A response is timed against the request that preceded it."""
        from ui.widgets.live_trace_widget import LiveTraceWidget

        trace = LiveTraceWidget()
        qtbot.addWidget(trace)
        trace.add_frame("TX", bytes.fromhex("22F190"))
        response = trace.add_frame("RX", bytes.fromhex("62F19057"))
        assert response is not None
        assert response.elapsed_ms >= 0.0
        assert trace.last_response() == bytes.fromhex("62F19057")

    def test_live_trace_pause_and_capacity(self, qtbot) -> None:
        """Pausing stops ingestion and the ring buffer never grows unbounded."""
        from ui.widgets.live_trace_widget import LiveTraceWidget

        trace = LiveTraceWidget(capacity=10)
        qtbot.addWidget(trace)
        trace.set_paused(True)
        assert trace.add_frame("TX", bytes.fromhex("22F190")) is None
        assert not trace.rows

        trace.set_paused(False)
        for _ in range(25):
            trace.add_frame("TX", bytes.fromhex("22F190"))
        assert len(trace.rows) == 10
        assert trace.table.rowCount() == 10

        trace.clear()
        assert not trace.rows
        assert trace.table.rowCount() == 0

    def test_trace_double_click_loads_the_slicer(self, qtbot) -> None:
        """A traced frame can be sent straight back into the slicer."""
        from ui.panels.data_analysis_panel.data_analysis_workspace import DataAnalysisWorkspace

        workspace = DataAnalysisWorkspace()
        qtbot.addWidget(workspace)
        payload = bytes.fromhex("62F1905742415A")
        workspace.trace.frame_activated.emit(payload)
        assert workspace.slicer_panel.slicer.data() == payload

    def test_byte_map_shows_both_rows(self, qtbot) -> None:
        """The byte map is tall enough for the Byte *and* the Slice row."""
        from ui.widgets.data_slicer_widget import DataSlicerWidget

        widget = DataSlicerWidget()
        qtbot.addWidget(widget)
        widget.show()
        qtbot.waitExposed(widget)
        widget.set_data(bytes.fromhex("62F190574241315A"))
        widget.auto_detect()
        table = widget.byte_map
        viewport = table.viewport().height()
        for row in (0, 1):
            bottom = table.rowViewportPosition(row) + table.rowHeight(row)
            assert bottom <= viewport, f"byte map row {row} is clipped"

    def test_log_controller_feeds_the_live_trace(self, qtbot, config, event_bus) -> None:
        """Communication entries reach the trace strip through the controller."""
        from src.core.models.log_entry_model import LogEntry
        from src.logging_system.log_manager import LogManager
        from ui.controllers.log_controller import LogController
        from ui.panels.log_panel.log_viewer_panel import LogViewerPanel
        from ui.widgets.live_trace_widget import LiveTraceWidget

        panel = LogViewerPanel()
        trace = LiveTraceWidget()
        qtbot.addWidget(panel)
        qtbot.addWidget(trace)
        manager = LogManager(config, event_bus, use_file=False, use_database=False)
        controller = LogController(panel, manager, None, live_trace=trace)

        controller._on_entry(LogEntry(direction="TX", data=bytes.fromhex("22F190")))
        controller._on_entry(LogEntry(direction="RX", data=bytes.fromhex("62F19057")))
        controller._on_entry(LogEntry(message="not communication"))
        controller._flush()

        assert len(trace.rows) == 2
        assert trace.last_response() == bytes.fromhex("62F19057")

    def test_trace_viewer_pairs_diagnostic_entries(self, qtbot) -> None:
        """The offline trace viewer now finds exchanges it used to miss.

        ``DiagnosticLogger`` did not stamp a direction, so ``analyse`` saw no
        TX entry to open an exchange with and always produced an empty table.
        """
        from src.core.event_bus import Event, EventType
        from src.logging_system.diagnostic_logger import DiagnosticLogger
        from ui.panels.log_panel.trace_viewer_panel import TraceViewerPanel

        captured: list = []
        logger = DiagnosticLogger(sink=captured.append)
        logger._on_event(
            Event(type=EventType.DIAG_REQUEST_SENT, data={"payload": bytes.fromhex("22F190")})
        )
        logger._on_event(
            Event(
                type=EventType.DIAG_RESPONSE_RECEIVED,
                data={"payload": bytes.fromhex("62F19057")},
            )
        )
        assert [e.direction for e in captured] == ["TX", "RX"]

        panel = TraceViewerPanel()
        qtbot.addWidget(panel)
        exchanges = panel.analyse(captured)
        assert len(exchanges) == 1
        assert exchanges[0].response is not None


class TestChannelSelector:
    """The channel control must offer identifiers the backend can use.

    SocketCAN binds to a kernel interface *name*; every other family indexes
    a vendor device table. One shared list of ``0..7`` produced
    ``sock.bind(("0",))``, which can never succeed.
    """

    def test_socketcan_offers_interface_names(self, qtbot) -> None:
        """Selecting SocketCAN replaces the indices with can/vcan names."""
        from src.core.enums.vci_enums import VCIType
        from ui.panels.connection_panel.connection_panel import ConnectionPanel

        panel = ConnectionPanel()
        qtbot.addWidget(panel)
        panel.vci_box.setCurrentIndex(panel.vci_box.findData(VCIType.SOCKETCAN.value))
        choices = [panel.channel_box.itemText(i) for i in range(panel.channel_box.count())]
        assert "can0" in choices
        assert "vcan0" in choices
        assert "0" not in choices
        assert panel.profile().channel == "can0"

    def test_other_families_keep_numeric_channels(self, qtbot) -> None:
        """A vendor interface still selects a numeric channel index."""
        from src.core.enums.vci_enums import VCIType
        from ui.panels.connection_panel.connection_panel import ConnectionPanel

        panel = ConnectionPanel()
        qtbot.addWidget(panel)
        for vci_type in (VCIType.PCAN, VCIType.KVASER_LEAF_V3, VCIType.VECTOR):
            panel.vci_box.setCurrentIndex(panel.vci_box.findData(vci_type.value))
            choices = [panel.channel_box.itemText(i) for i in range(panel.channel_box.count())]
            assert choices[:3] == ["0", "1", "2"], vci_type

    def test_channel_is_editable_for_custom_links(self, qtbot) -> None:
        """An operator can type a link name the preset list does not know."""
        from src.core.enums.vci_enums import VCIType
        from ui.panels.connection_panel.connection_panel import ConnectionPanel

        panel = ConnectionPanel()
        qtbot.addWidget(panel)
        panel.vci_box.setCurrentIndex(panel.vci_box.findData(VCIType.SOCKETCAN.value))
        assert panel.channel_box.isEditable()
        panel.channel_box.setCurrentText("can7")
        assert panel.profile().channel == "can7"

    def test_ui_channel_reaches_the_driver_correctly(self, qtbot) -> None:
        """End to end: what the panel produces is what the backend expects."""
        from src.communication.vci_drivers.pcan.pcan_driver import (
            PCANDriver,
            PythonCanDriver,
        )
        from src.core.enums.vci_enums import VCIType
        from src.core.models.vci_model import VCIChannelConfig
        from ui.panels.connection_panel.connection_panel import ConnectionPanel

        panel = ConnectionPanel()
        qtbot.addWidget(panel)

        panel.vci_box.setCurrentIndex(panel.vci_box.findData(VCIType.PCAN.value))
        panel.channel_box.setCurrentText("2")
        channel = panel.profile().channel
        assert PCANDriver(VCIChannelConfig(channel=channel))._channel_argument() == "PCAN_USBBUS2"

        panel.vci_box.setCurrentIndex(panel.vci_box.findData(VCIType.SOCKETCAN.value))
        channel = panel.profile().channel
        driver = PythonCanDriver("socketcan", VCIChannelConfig(channel=channel))
        assert driver._channel_argument() == "can0"


class TestVCIErrorReporting:
    """A failed hardware connection must be explained, not just reported."""

    def _error(self, vci_type, channel="1"):
        from src.communication.vci_drivers.vci_factory import VCIFactory
        from src.core.exceptions import ConnectionFailedError, DriverNotFoundError
        from src.core.models.vci_model import VCIChannelConfig

        driver = VCIFactory.create(
            vci_type,
            VCIChannelConfig(channel=channel, bitrate=500_000),
            fallback_to_virtual=False,
        )
        try:
            driver.connect()
        except (ConnectionFailedError, DriverNotFoundError) as exc:
            return exc
        driver.disconnect()
        return None

    def test_every_backend_reports_an_actionable_hint(self) -> None:
        """No sandbox has this hardware, so each must fail with guidance."""
        from src.core.enums.vci_enums import VCIType

        for vci_type in (
            VCIType.PCAN,
            VCIType.VECTOR,
            VCIType.KVASER_LEAF_V3,
            VCIType.SOCKETCAN,
            VCIType.INTREPIDCS,
        ):
            error = self._error(vci_type)
            assert error is not None, vci_type
            assert error.details.get("hint"), vci_type
            assert error.details.get("channel") is not None, vci_type

    def test_socketcan_hint_names_the_link_and_bitrate(self) -> None:
        """The hint is a command the operator can paste into a terminal."""
        from src.core.enums.vci_enums import VCIType

        error = self._error(VCIType.SOCKETCAN, channel="can0")
        assert error is not None
        assert error.details["hint"] == (
            "bring the link up: sudo ip link set can0 up type can bitrate 500000"
        )

    def test_dialog_shows_a_clean_headline_and_the_hint(self, qtbot) -> None:
        """The headline is the message; the hint drives the recovery field."""
        from src.core.enums.vci_enums import VCIType
        from ui.dialogs.error_dialog import ErrorDialog

        error = self._error(VCIType.PCAN)
        assert error is not None
        dialog = ErrorDialog.from_exception(error)
        qtbot.addWidget(dialog)
        # The headline must not carry the whole details mapping.
        assert dialog.recovery_label.text() == error.details["hint"]
        assert dialog.recovery_label.isVisibleTo(dialog)
        assert "hint=" not in error.message
        assert "PCAN_USBBUS1" in error.message
        # The structured context is still available for a bug report.
        assert "hint:" in dialog.details_text

    def test_factory_never_silently_substitutes_virtual(self) -> None:
        """Fallback must be opt-in, or a broken bench looks healthy."""
        from src.communication.vci_drivers.vci_factory import VCIFactory
        from src.core.enums.vci_enums import VCIType
        from src.core.models.vci_model import VCIChannelConfig

        config = VCIChannelConfig(channel="1", bitrate=500_000)
        driver = VCIFactory.create(VCIType.PCAN, config, fallback_to_virtual=False)
        assert type(driver).__name__ == "PCANDriver"
