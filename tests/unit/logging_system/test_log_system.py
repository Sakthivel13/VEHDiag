"""Unit tests for the logging subsystem."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.models.log_entry_model import LogCategory, LogEntry, LogLevel
from src.logging_system.communication_logger import decode_uds
from src.logging_system.log_database import LogDatabase
from src.logging_system.log_exporter import ExportFormat, LogExporter
from src.logging_system.log_filter import QUICK_FILTERS, LogFilter
from src.logging_system.log_formatter import FormatOptions, LogFormatter
from src.logging_system.log_manager import LogManager


@pytest.fixture()
def manager(config, event_bus) -> LogManager:
    """Return an in-memory log manager."""
    instance = LogManager(config, event_bus, buffer_size=1000, use_file=False, use_database=False)
    yield instance
    instance.close()


class TestLogManager:
    """The central manager."""

    def test_levels(self, manager: LogManager) -> None:
        """Entries below the level are dropped."""
        manager.set_level(LogLevel.WARNING)
        manager.debug("ignored")
        manager.warning("kept")
        assert manager.count() == 1

    def test_categories(self, manager: LogManager) -> None:
        """The category is recorded."""
        manager.info("comm", category=LogCategory.COMM)
        assert manager.entries()[0].category is LogCategory.COMM

    def test_pause_and_resume(self, manager: LogManager) -> None:
        """Paused logging drops entries."""
        manager.pause()
        manager.info("dropped")
        manager.resume()
        manager.info("kept")
        assert manager.count() == 1

    def test_listeners(self, manager: LogManager) -> None:
        """Listeners receive every entry."""
        received: list[LogEntry] = []
        manager.add_listener(received.append)
        manager.info("hello")
        assert len(received) == 1

    def test_clear(self, manager: LogManager) -> None:
        """Clearing empties the buffer."""
        manager.info("first")
        manager.clear()
        assert manager.count() == 0

    def test_search(self, manager: LogManager) -> None:
        """Full text search finds the entry."""
        manager.info("connection established")
        manager.info("something else")
        assert len(manager.search("connection")) == 1

    def test_delta_timestamps(self, manager: LogManager) -> None:
        """Consecutive entries carry a delta."""
        manager.info("first")
        manager.info("second")
        assert manager.entries()[1].delta_us >= 0


class TestLogFilter:
    """Filtering."""

    def test_level_filter(self) -> None:
        """Only entries at or above the level pass."""
        log_filter = LogFilter(min_level=LogLevel.WARNING)
        assert not log_filter.matches(LogEntry(level=LogLevel.INFO))
        assert log_filter.matches(LogEntry(level=LogLevel.ERROR))

    def test_direction_filter(self) -> None:
        """The direction can be restricted."""
        log_filter = LogFilter(directions={"TX"})
        assert log_filter.matches(LogEntry(direction="TX"))
        assert not log_filter.matches(LogEntry(direction="RX"))

    def test_data_pattern(self) -> None:
        """A hex pattern must appear in the payload."""
        log_filter = LogFilter(data_pattern="F190")
        assert log_filter.matches(LogEntry(data=bytes.fromhex("22F190")))
        assert not log_filter.matches(LogEntry(data=bytes.fromhex("221234")))

    def test_identifier_range(self) -> None:
        """Identifiers outside the range are dropped."""
        log_filter = LogFilter(id_from=0x700, id_to=0x7FF)
        assert log_filter.matches(LogEntry(can_id="0x7E0"))
        assert not log_filter.matches(LogEntry(can_id="0x100"))

    def test_hide_tester_present(self) -> None:
        """Keep-alive traffic can be hidden."""
        log_filter = LogFilter(hide_tester_present=True)
        assert not log_filter.matches(LogEntry(data=bytes.fromhex("023E80")))
        assert log_filter.matches(LogEntry(data=bytes.fromhex("0322F190")))

    def test_quick_filters(self) -> None:
        """The quick filters are usable."""
        assert QUICK_FILTERS["Errors only"].matches(LogEntry(level=LogLevel.ERROR))
        assert not QUICK_FILTERS["Errors only"].matches(LogEntry(level=LogLevel.INFO))

    def test_serialisation(self) -> None:
        """A filter survives a round trip."""
        original = LogFilter(min_level=LogLevel.WARNING, directions={"TX"}, contains="test")
        restored = LogFilter.from_dict(original.to_dict())
        assert restored.min_level is LogLevel.WARNING
        assert restored.contains == "test"


class TestDatabase:
    """SQLite storage."""

    def test_insert_and_count(self) -> None:
        """Entries are persisted."""
        with LogDatabase(":memory:") as database:
            for index in range(10):
                database.insert(LogEntry(message=f"entry {index}"))
            database.flush()
            assert database.count() == 10

    def test_query_by_level(self) -> None:
        """Queries can filter by level."""
        with LogDatabase(":memory:") as database:
            database.insert(LogEntry(message="info", level=LogLevel.INFO))
            database.insert(LogEntry(message="error", level=LogLevel.ERROR))
            database.flush()
            assert len(database.query(level="ERROR")) == 1

    def test_search(self) -> None:
        """Text search works on the message column."""
        with LogDatabase(":memory:") as database:
            database.insert(LogEntry(message="connection established"))
            database.flush()
            assert len(database.search("connection")) == 1

    def test_round_trip_preserves_data(self) -> None:
        """Payload bytes survive the storage."""
        with LogDatabase(":memory:") as database:
            database.insert(LogEntry(data=bytes.fromhex("22F190"), can_id="0x7E0", direction="TX"))
            database.flush()
            restored = database.query()[0]
            assert restored.data == bytes.fromhex("22F190")
            assert restored.can_id == "0x7E0"

    def test_statistics(self) -> None:
        """The statistics group by level and category."""
        with LogDatabase(":memory:") as database:
            database.insert(LogEntry(level=LogLevel.ERROR))
            database.insert(LogEntry(level=LogLevel.INFO))
            database.flush()
            statistics = database.statistics()
            assert statistics["total"] == 2
            assert statistics["levels"]["ERROR"] == 1


class TestExport:
    """Exporting."""

    @pytest.fixture()
    def entries(self) -> list[LogEntry]:
        """Return a small set of communication entries."""
        return [
            LogEntry(direction="TX", protocol="CAN", can_id="0x7E0",
                     data=bytes.fromhex("0310030000000000"), decoded_service="Session"),
            LogEntry(direction="RX", protocol="CAN", can_id="0x7E8",
                     data=bytes.fromhex("0650030032010000"), decoded_service="Session response"),
        ]

    @pytest.mark.parametrize(
        "fmt", [ExportFormat.CSV, ExportFormat.JSON, ExportFormat.XML, ExportFormat.TEXT,
                ExportFormat.HTML, ExportFormat.ASC, ExportFormat.PCAP]
    )
    def test_every_format(self, tmp_path: Path, entries: list[LogEntry], fmt: ExportFormat) -> None:
        """Every export format produces a non-empty file."""
        target = LogExporter().export(entries, tmp_path / f"log{fmt.suffix}", fmt)
        assert target.exists()
        assert target.stat().st_size > 0

    def test_json_structure(self, tmp_path: Path, entries: list[LogEntry]) -> None:
        """The JSON export is a list of entry mappings."""
        target = LogExporter().export(entries, tmp_path / "log.json", ExportFormat.JSON)
        payload = json.loads(target.read_text())
        assert len(payload) == 2
        assert payload[0]["direction"] == "TX"

    def test_csv_header(self, tmp_path: Path, entries: list[LogEntry]) -> None:
        """The CSV export starts with the header row."""
        target = LogExporter().export(entries, tmp_path / "log.csv", ExportFormat.CSV)
        assert target.read_text().splitlines()[0].startswith("timestamp")

    def test_progress_callback(self, tmp_path: Path, entries: list[LogEntry]) -> None:
        """The progress callback is invoked."""
        seen: list[tuple[int, int]] = []
        LogExporter().export(
            entries, tmp_path / "log.csv", ExportFormat.CSV, on_progress=lambda d, t: seen.append((d, t))
        )
        assert seen[-1] == (2, 2)


class TestDecoding:
    """UDS decoding of logged frames."""

    @pytest.mark.parametrize(
        ("payload", "expected"),
        [
            ("22F190", "ReadDataByIdentifier"),
            ("62F190", "ReadDataByIdentifier response"),
            ("1003", "DiagnosticSessionControl"),
            ("7F2231", "NegativeResponse"),
            ("3E80", "TesterPresent"),
        ],
    )
    def test_service_names(self, payload: str, expected: str) -> None:
        """Requests and responses are decoded."""
        assert decode_uds(bytes.fromhex(payload))[0] == expected

    def test_did_detail(self) -> None:
        """The DID is shown as a detail."""
        assert decode_uds(bytes.fromhex("22F190"))[1] == "DID 0xF190"

    def test_formatter_text(self) -> None:
        """The formatter renders a readable line."""
        entry = LogEntry(direction="TX", protocol="CAN", can_id="0x7E0",
                         data=bytes.fromhex("22F190"), decoded_service="ReadDataByIdentifier")
        text = LogFormatter(FormatOptions()).to_text(entry)
        assert "TX" in text and "22 F1 90" in text


class TestDiagnosticLoggerDirection:
    """Diagnostic entries must be tagged TX/RX.

    Without a direction the trace viewer, the live trace strip and the
    communication export all treat a UDS exchange as a plain text line and
    silently drop it, which made the trace look permanently empty.
    """

    def test_request_and_response_are_directional(self) -> None:
        """``DIAG_REQUEST_SENT`` is TX and ``DIAG_RESPONSE_RECEIVED`` is RX."""
        from src.core.event_bus import Event, EventType
        from src.logging_system.diagnostic_logger import DiagnosticLogger

        captured: list = []
        logger = DiagnosticLogger(sink=captured.append)

        logger._on_event(
            Event(type=EventType.DIAG_REQUEST_SENT, data={"payload": bytes.fromhex("22F190")})
        )
        logger._on_event(
            Event(
                type=EventType.DIAG_RESPONSE_RECEIVED,
                data={"payload": bytes.fromhex("62F19057"), "elapsed_ms": 3.5},
            )
        )
        logger._on_event(
            Event(type=EventType.DIAG_NRC_RECEIVED, data={"payload": bytes.fromhex("7F2233")})
        )

        assert [entry.direction for entry in captured] == ["TX", "RX", "RX"]
        assert captured[0].data == bytes.fromhex("22F190")
        assert captured[0].decoded_service == "ReadDataByIdentifier"

    def test_events_without_payload_stay_undirected(self) -> None:
        """A status-only event is not communication and carries no direction."""
        from src.core.event_bus import Event, EventType
        from src.logging_system.diagnostic_logger import DiagnosticLogger

        captured: list = []
        DiagnosticLogger(sink=captured.append)._on_event(
            Event(type=EventType.DIAG_DTC_CLEARED, data={"group": 0xFFFFFF})
        )
        assert captured[0].direction == ""
