"""Export log entries to CSV, JSON, XML, text, ASC, BLF, HTML and PCAP."""
from __future__ import annotations

import csv
import io
import json
import logging
import struct
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable

from ..core.models.log_entry_model import LogEntry
from ..utils.file_utils import ensure_dir
from .log_formatter import FormatOptions, LogFormatter

_logger = logging.getLogger(__name__)


class ExportFormat(str, Enum):
    """Supported export formats."""

    CSV = "CSV"
    JSON = "JSON"
    XML = "XML"
    TEXT = "TEXT"
    ASC = "ASC"
    BLF = "BLF"
    HTML = "HTML"
    PCAP = "PCAP"

    @property
    def suffix(self) -> str:
        """Return the conventional file suffix of the format."""
        return {
            ExportFormat.CSV: ".csv",
            ExportFormat.JSON: ".json",
            ExportFormat.XML: ".xml",
            ExportFormat.TEXT: ".txt",
            ExportFormat.ASC: ".asc",
            ExportFormat.BLF: ".blf",
            ExportFormat.HTML: ".html",
            ExportFormat.PCAP: ".pcap",
        }[self]


@dataclass(slots=True)
class ExportOptions:
    """Options controlling an export run.

    Attributes:
        columns: CSV columns to include; empty means every column.
        delimiter: CSV delimiter.
        encoding: Text encoding of the output file.
        pretty: Pretty print JSON and XML.
        title: Title used by the HTML report.
        include_filtered_only: Export only the entries handed in.
    """

    columns: tuple[str, ...] = ()
    delimiter: str = ","
    encoding: str = "utf-8"
    pretty: bool = True
    title: str = "Diagnostic log"
    include_filtered_only: bool = True


class LogExporter:
    """Write log entries to a file in one of the supported formats.

    Example:
        >>> import tempfile, pathlib
        >>> from src.core.models.log_entry_model import LogEntry
        >>> exporter = LogExporter()
        >>> target = pathlib.Path(tempfile.mkdtemp()) / "log.csv"
        >>> _ = exporter.export([LogEntry(message="hello")], target, ExportFormat.CSV)
        >>> "hello" in target.read_text()
        True
    """

    def __init__(self, formatter: LogFormatter | None = None) -> None:
        """Create the exporter with an optional shared formatter."""
        self.formatter = formatter or LogFormatter(FormatOptions(absolute_time=True))
        self.cancelled = False

    def cancel(self) -> None:
        """Request cancellation of a running export."""
        self.cancelled = True

    def export(
        self,
        entries: Iterable[LogEntry],
        path: str | Path,
        export_format: ExportFormat | str = ExportFormat.CSV,
        options: ExportOptions | None = None,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> Path:
        """Write *entries* to *path* using the requested format.

        Args:
            entries: Entries to export.
            path: Destination file.
            export_format: Output format.
            options: Format specific options.
            on_progress: Callback receiving ``(done, total)``.

        Returns:
            The path that was written.

        Raises:
            ValueError: The format is not supported.
        """
        self.cancelled = False
        fmt = ExportFormat(export_format) if not isinstance(export_format, ExportFormat) else export_format
        opts = options or ExportOptions()
        items = list(entries)
        target = Path(path).expanduser()
        ensure_dir(target.parent)

        writers: dict[ExportFormat, Callable[[list[LogEntry], Path, ExportOptions, Callable[[int, int], None] | None], None]] = {
            ExportFormat.CSV: self._write_csv,
            ExportFormat.JSON: self._write_json,
            ExportFormat.XML: self._write_xml,
            ExportFormat.TEXT: self._write_text,
            ExportFormat.ASC: self._write_asc,
            ExportFormat.BLF: self._write_blf,
            ExportFormat.HTML: self._write_html,
            ExportFormat.PCAP: self._write_pcap,
        }
        writer = writers.get(fmt)
        if writer is None:
            raise ValueError(f"unsupported export format {fmt}")
        writer(items, target, opts, on_progress)
        _logger.info("exported %d entries to %s", len(items), target)
        return target

    # -- writers ------------------------------------------------------------
    def _write_csv(self, entries, path, options, on_progress) -> None:  # noqa: ANN001
        """Write the entries as CSV."""
        columns = list(options.columns) or self.formatter.csv_header()
        with path.open("w", newline="", encoding=options.encoding) as handle:
            writer = csv.writer(handle, delimiter=options.delimiter)
            writer.writerow(columns)
            for index, entry in enumerate(entries, start=1):
                if self.cancelled:
                    return
                mapping = entry.as_dict()
                writer.writerow([mapping.get(column, "") for column in columns])
                self._progress(on_progress, index, len(entries))

    def _write_json(self, entries, path, options, on_progress) -> None:  # noqa: ANN001
        """Write the entries as a JSON array."""
        payload = [entry.as_dict() for entry in entries]
        text = json.dumps(payload, indent=2 if options.pretty else None, default=str)
        path.write_text(text, encoding=options.encoding)
        self._progress(on_progress, len(entries), len(entries))

    def _write_xml(self, entries, path, options, on_progress) -> None:  # noqa: ANN001
        """Write the entries as an XML document."""
        root = ET.Element("diagnosticLog", attrib={"count": str(len(entries))})
        for index, entry in enumerate(entries, start=1):
            if self.cancelled:
                return
            element = ET.SubElement(root, "entry")
            for key, value in entry.as_dict().items():
                child = ET.SubElement(element, key)
                child.text = str(value)
            self._progress(on_progress, index, len(entries))
        tree = ET.ElementTree(root)
        if options.pretty:
            ET.indent(tree, space="  ")
        tree.write(path, encoding=options.encoding, xml_declaration=True)

    def _write_text(self, entries, path, options, on_progress) -> None:  # noqa: ANN001
        """Write the entries as formatted plain text."""
        buffer = io.StringIO()
        for index, entry in enumerate(entries, start=1):
            if self.cancelled:
                return
            buffer.write(self.formatter.to_text(entry) + "\n")
            self._progress(on_progress, index, len(entries))
        path.write_text(buffer.getvalue(), encoding=options.encoding)

    def _write_html(self, entries, path, options, on_progress) -> None:  # noqa: ANN001
        """Write a styled HTML report."""
        path.write_text(self.formatter.html_document(entries, options.title), encoding=options.encoding)
        self._progress(on_progress, len(entries), len(entries))

    def _write_asc(self, entries, path, options, on_progress) -> None:  # noqa: ANN001
        """Write a Vector CANalyzer compatible ASC trace."""
        from .asc_logger import ASCLogger

        ASCLogger(path).write_entries(entries)
        self._progress(on_progress, len(entries), len(entries))

    def _write_blf(self, entries, path, options, on_progress) -> None:  # noqa: ANN001
        """Write a Vector BLF trace (falls back to ASC when unsupported)."""
        from .blf_logger import BLFLogger

        BLFLogger(path).write_entries(entries)
        self._progress(on_progress, len(entries), len(entries))

    def _write_pcap(self, entries, path, options, on_progress) -> None:  # noqa: ANN001
        """Write a PCAP file for Ethernet/DoIP traffic."""
        from .pcap_logger import PcapLogger

        PcapLogger(path).write_entries(entries)
        self._progress(on_progress, len(entries), len(entries))

    @staticmethod
    def _progress(callback: Callable[[int, int], None] | None, done: int, total: int) -> None:
        """Invoke the progress callback if one was supplied."""
        if callback is not None:
            callback(done, total)


__all__ = ["LogExporter", "ExportFormat", "ExportOptions"]
