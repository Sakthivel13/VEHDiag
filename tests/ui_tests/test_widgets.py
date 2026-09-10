"""Tests for the custom widgets."""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402

from src.core.models.dtc_model import DTC, DTCReport  # noqa: E402
from src.core.models.log_entry_model import LogEntry  # noqa: E402
from src.core.models.test_sequence_model import TestResult, TestStatus  # noqa: E402

pytestmark = pytest.mark.ui


class TestHexInputField:
    """The validated hexadecimal entry field."""

    def test_auto_formatting(self, qtbot, scaler) -> None:
        """Digits are grouped in pairs automatically."""
        from ui.widgets.hex_input_field import HexInputField

        field = HexInputField(scaler=scaler)
        qtbot.addWidget(field)
        field.setText("22f190")
        assert field.text() == "22 F1 90"
        assert field.value() == bytes.fromhex("22F190")

    def test_length_validation(self, qtbot, scaler) -> None:
        """The validity flag follows the configured bounds."""
        from ui.widgets.hex_input_field import HexInputField

        field = HexInputField(scaler=scaler, min_bytes=2, max_bytes=2)
        qtbot.addWidget(field)
        field.setText("F1")
        assert not field.is_valid
        field.setText("F190")
        assert field.is_valid

    def test_non_hex_is_stripped(self, qtbot, scaler) -> None:
        """Pasted noise is removed."""
        from ui.widgets.hex_input_field import HexInputField

        field = HexInputField(scaler=scaler)
        qtbot.addWidget(field)
        field.setText("0x22:F1-90 xyz")
        assert field.value() == bytes.fromhex("22F190")

    def test_signals(self, qtbot, scaler) -> None:
        """Changing the text emits the parsed bytes."""
        from ui.widgets.hex_input_field import HexInputField

        field = HexInputField(scaler=scaler)
        qtbot.addWidget(field)
        with qtbot.waitSignal(field.bytes_changed) as blocker:
            field.setText("1003")
        assert blocker.args[0] == b"\x10\x03"


class TestDataWidgets:
    """The converter, slicer and byte editor."""

    def test_converter_shows_every_format(self, qtbot, scaler) -> None:
        """All representations appear in the results table."""
        from ui.widgets.data_converter_widget import DataConverterWidget

        widget = DataConverterWidget(scaler=scaler)
        qtbot.addWidget(widget)
        widget.set_data(b"ABCD")
        values = {
            widget.results.item(row, 0).text(): widget.results.item(row, 1).text()
            for row in range(widget.results.rowCount())
        }
        assert values["HEX"] == "41 42 43 44"
        assert values["ASCII"] == "ABCD"
        assert "DEC_UNSIGNED_BE" in values

    def test_slicer_auto_detect(self, qtbot, scaler) -> None:
        """The slicer recognises a ReadDataByIdentifier response."""
        from ui.widgets.data_slicer_widget import DataSlicerWidget

        widget = DataSlicerWidget(scaler=scaler)
        qtbot.addWidget(widget)
        widget.set_data(bytes.fromhex("62F1905742415A"))
        widget.auto_detect()
        values = widget.values()
        assert values["Service echo"] == "62"
        assert values["Data identifier"] == "F1 90"

    def test_slicer_manual_slice(self, qtbot, scaler) -> None:
        """Slices can be added programmatically."""
        from ui.widgets.data_slicer_widget import DataSlicerWidget

        widget = DataSlicerWidget(scaler=scaler)
        qtbot.addWidget(widget)
        widget.set_data(bytes.fromhex("0102030405"))
        widget.add_slice(1, 2, "middle")
        assert widget.values()["middle"] == "02 03"

    def test_byte_array_editor(self, qtbot, scaler) -> None:
        """The editor exposes the byte array it displays."""
        from ui.widgets.byte_array_editor import ByteArrayEditor

        widget = ByteArrayEditor(scaler=scaler)
        qtbot.addWidget(widget)
        widget.set_data(bytes(range(20)))
        assert widget.data() == bytes(range(20))
        assert widget.table.rowCount() == 2


class TestLogViewer:
    """The virtual scrolling log viewer."""

    def test_large_dataset(self, qtbot, scaler) -> None:
        """A hundred thousand entries load without a problem."""
        from ui.widgets.log_viewer_widget import LogViewerWidget

        widget = LogViewerWidget(scaler=scaler)
        qtbot.addWidget(widget)
        entries = [
            LogEntry(direction="TX", protocol="CAN", can_id="0x7E0", data=b"\x02\x10\x03")
            for _ in range(100_000)
        ]
        widget.set_entries(entries)
        assert widget.entry_count() == 100_000

    def test_cell_rendering(self, qtbot, scaler) -> None:
        """Cells render the expected text."""
        from ui.widgets.log_viewer_widget import LogViewerWidget

        widget = LogViewerWidget(scaler=scaler)
        qtbot.addWidget(widget)
        widget.set_entries([LogEntry(direction="TX", protocol="CAN", can_id="0x7E0",
                                     data=bytes.fromhex("22F190"))])
        model = widget.model
        assert model.data(model.index(0, 2)) == "TX"
        assert model.data(model.index(0, 5)) == "22 F1 90"

    def test_batching(self, qtbot, scaler) -> None:
        """Queued entries appear after a flush."""
        from ui.widgets.log_viewer_widget import LogViewerWidget

        widget = LogViewerWidget(scaler=scaler)
        qtbot.addWidget(widget)
        for _ in range(10):
            widget.add_entry(LogEntry(message="test"))
        widget._flush()
        assert widget.entry_count() == 10


class TestStatusWidgets:
    """LED, progress and status bar."""

    def test_led_states(self, qtbot, scaler) -> None:
        """Each state maps to its colour."""
        from ui.widgets.led_indicator import LedIndicator

        led = LedIndicator(scaler=scaler)
        qtbot.addWidget(led)
        led.set_state("pass")
        assert led.color == "#22C55E"
        led.set_state("fail")
        assert led.color == "#EF4444"

    def test_progress_widget(self, qtbot, scaler) -> None:
        """The progress widget shows speed and ETA."""
        import time

        from src.core.enums.transfer_enums import TransferState
        from src.core.models.file_transfer_model import TransferProgress
        from ui.widgets.progress_widget import ProgressWidget

        widget = ProgressWidget(scaler=scaler)
        qtbot.addWidget(widget)
        widget.update_progress(
            TransferProgress(
                state=TransferState.TRANSFERRING,
                bytes_total=1000,
                bytes_done=500,
                started_at=time.time() - 1,
            )
        )
        assert widget.bar.value() == 50
        assert "/s" in widget.speed_label.text()

    def test_status_bar(self, qtbot, scaler) -> None:
        """The status bar reflects the session and the counters."""
        from ui.widgets.status_bar_widget import StatusBarWidget

        bar = StatusBarWidget(scaler=scaler)
        qtbot.addWidget(bar)
        bar.set_session("extended")
        bar.set_security(True, 1)
        bar.set_counters(10, 8)
        assert "extended" in bar.session_label.text()
        assert "Unlocked" in bar.security_label.text()
        assert bar.counter_label.text() == "TX 10 / RX 8"


class TestDragAndDrop:
    """Reordering the developer mode cards."""

    def test_list_reorder(self, qtbot, scaler) -> None:
        """The list widget reorders its rows."""
        from ui.widgets.drag_drop_list_widget import DragDropListWidget

        widget = DragDropListWidget(scaler=scaler)
        qtbot.addWidget(widget)
        widget.add_items(["a", "b", "c"])
        with qtbot.waitSignal(widget.order_changed):
            widget.move_item(0, 2)
        assert widget.order() == ["b", "c", "a"]

    def test_sequence_editor_reorder(self, qtbot, scaler) -> None:
        """Moving a card renumbers the sequence."""
        from src.test_execution.test_sequence_manager import TestSequenceManager
        from ui.panels.developer_panel.test_sequence_editor import TestSequenceEditor

        editor = TestSequenceEditor(scaler=scaler)
        qtbot.addWidget(editor)
        editor.load_sequence(TestSequenceManager().create_default())
        first = editor.cards[0].step.name
        editor.move_card(0, 2)
        assert editor.cards[2].step.name == first
        assert [card.step.order for card in editor.cards[:3]] == [1, 2, 3]

    def test_card_reflects_results(self, qtbot, scaler) -> None:
        """A result updates the card status."""
        from src.test_execution.test_sequence_manager import TestSequenceManager
        from ui.panels.developer_panel.test_sequence_editor import TestSequenceEditor

        editor = TestSequenceEditor(scaler=scaler)
        qtbot.addWidget(editor)
        editor.load_sequence(TestSequenceManager().create_default())
        step = editor.cards[0].step
        editor.apply_result(TestResult(step, TestStatus.PASS, 12.5))
        assert editor.cards[0].status_label.text() == "Pass"
        assert "12.5" in editor.cards[0].duration_label.text()


class TestPanels:
    """The diagnostic panels."""

    def test_dtc_panel_shows_report(self, qtbot, scaler) -> None:
        """The results table lists every DTC."""
        from ui.panels.diagnostic_panel.read_dtc_panel.read_dtc_view import ReadDTCView

        view = ReadDTCView(scaler=scaler)
        qtbot.addWidget(view)
        report = DTCReport(
            0x02,
            [
                DTC.from_bytes(bytes.fromhex("C07300"), 0x2F, "Steering"),
                DTC.from_bytes(bytes.fromhex("010000"), 0x24, "MAF"),
            ],
        )
        view.show_report(report)
        assert view.results_table.rowCount() == 2
        assert "2 DTC(s)" in view.count_label.text()

    def test_dtc_status_mask(self, qtbot, scaler) -> None:
        """The checkboxes assemble the status mask."""
        from ui.panels.diagnostic_panel.read_dtc_panel.read_dtc_view import ReadDTCView

        view = ReadDTCView(scaler=scaler)
        qtbot.addWidget(view)
        for box in view.mask_boxes.values():
            box.setChecked(False)
        view.mask_boxes[3].setChecked(True)
        assert view.status_mask() == 0x08

    def test_connection_panel_profile(self, qtbot, scaler) -> None:
        """The panel builds a valid connection profile."""
        from ui.panels.connection_panel.connection_panel import ConnectionPanel

        panel = ConnectionPanel(scaler=scaler)
        qtbot.addWidget(panel)
        profile = panel.profile()
        assert profile.tx_id == 0x7E0
        assert profile.rx_id == 0x7E8
        assert profile.protocol.value == "CAN"

    def test_connection_panel_protocol_pages(self, qtbot, scaler) -> None:
        """Selecting a protocol shows the matching configuration page."""
        from ui.panels.connection_panel.connection_panel import ConnectionPanel

        panel = ConnectionPanel(scaler=scaler)
        qtbot.addWidget(panel)
        panel.protocol_box.setCurrentIndex(panel.protocol_box.findData("DOIP"))
        assert panel.stack.currentIndex() == 1
        panel.protocol_box.setCurrentIndex(panel.protocol_box.findData("KLINE"))
        assert panel.stack.currentIndex() == 2

    def test_diagnostic_panel_tabs(self, qtbot, scaler) -> None:
        """Every service has its own tab."""
        from ui.panels.diagnostic_panel.diagnostic_main_panel import DiagnosticMainPanel

        panel = DiagnosticMainPanel(scaler=scaler)
        qtbot.addWidget(panel)
        # One tab per registered service view; asserting the mapping rather
        # than a literal keeps the test valid as services are added.
        assert panel.tabs.count() == len(panel.views)
        for title in ("Session", "Read DID", "Read DTC", "ECU flashing"):
            assert title in panel.views
        assert panel.show_view("Read DTC")

    def test_settings_panel_binding(self, qtbot, scaler, config) -> None:
        """Applying the settings writes into the configuration."""
        from ui.panels.settings_panel.settings_main_panel import SettingsMainPanel

        panel = SettingsMainPanel(scaler=scaler, config=config)
        qtbot.addWidget(panel)
        panel.editors["ui.theme"].setCurrentText("light")
        panel.apply()
        assert config.get("ui.theme") == "light"
