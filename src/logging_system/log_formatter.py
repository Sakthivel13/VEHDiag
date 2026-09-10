"""Log entry formatting for text, HTML and CSV output."""
from __future__ import annotations

import html
from dataclasses import dataclass

from ..core.models.log_entry_model import LogEntry, LogLevel

#: Colours used by the HTML report, matching the dark theme.
LEVEL_COLORS: dict[str, str] = {
    "TRACE": "#64748B",
    "DEBUG": "#94A3B8",
    "INFO": "#F8FAFC",
    "WARNING": "#F59E0B",
    "ERROR": "#EF4444",
    "CRITICAL": "#DC2626",
}

#: Colours used for the direction column of communication entries.
DIRECTION_COLORS: dict[str, str] = {"TX": "#06B6D4", "RX": "#22C55E"}


@dataclass(slots=True)
class FormatOptions:
    """Options controlling the rendering of a log entry.

    Attributes:
        show_timestamp: Include the timestamp column.
        absolute_time: Use ISO 8601 instead of ``HH:MM:SS.ffffff``.
        show_delta: Include the time difference to the previous entry.
        show_level: Include the severity column.
        show_category: Include the category column.
        show_decoded: Include the decoded service annotation.
        hex_separator: Separator between hexadecimal bytes.
    """

    show_timestamp: bool = True
    absolute_time: bool = False
    show_delta: bool = False
    show_level: bool = True
    show_category: bool = True
    show_decoded: bool = True
    hex_separator: str = " "


class LogFormatter:
    """Render :class:`LogEntry` objects as text, HTML or CSV rows.

    Example:
        >>> from src.core.models.log_entry_model import LogEntry, LogCategory
        >>> entry = LogEntry(message="connected", category=LogCategory.SYSTEM)
        >>> "connected" in LogFormatter().to_text(entry)
        True
    """

    #: Column order used by :meth:`to_csv_row` and :meth:`csv_header`.
    CSV_COLUMNS = (
        "timestamp",
        "level",
        "category",
        "direction",
        "protocol",
        "channel",
        "can_id",
        "data_hex",
        "data_length",
        "decoded_service",
        "delta_us",
        "message",
    )

    def __init__(self, options: FormatOptions | None = None) -> None:
        """Store the formatting options."""
        self.options = options or FormatOptions()

    def to_text(self, entry: LogEntry) -> str:
        """Render *entry* as a single plain text line."""
        parts: list[str] = []
        if self.options.show_timestamp:
            parts.append(entry.formatted_time(self.options.absolute_time))
        if self.options.show_delta and entry.delta_us:
            parts.append(f"(+{entry.delta_us / 1000.0:8.3f} ms)")
        if self.options.show_level:
            parts.append(f"[{entry.level.name:<8}]")
        if self.options.show_category:
            parts.append(f"[{entry.category.value:<6}]")
        if entry.data:
            parts.append(f"{entry.direction:<2}")
            if entry.protocol:
                parts.append(entry.protocol)
            if entry.can_id:
                parts.append(entry.can_id)
            parts.append(f"[{len(entry.data)}]")
            parts.append(
                self.options.hex_separator.join(f"{b:02X}" for b in entry.data)
            )
            if self.options.show_decoded and entry.decoded_service:
                parts.append(f"; {entry.decoded_service}")
        elif entry.message:
            parts.append(entry.message)
        return " ".join(parts)

    def to_html_row(self, entry: LogEntry) -> str:
        """Render *entry* as one ``<tr>`` of the HTML report."""
        colour = LEVEL_COLORS.get(entry.level.name, "#F8FAFC")
        direction_colour = DIRECTION_COLORS.get(entry.direction, colour)
        cells = [
            entry.formatted_time(self.options.absolute_time),
            f'<span style="color:{colour}">{entry.level.name}</span>',
            entry.category.value,
            f'<span style="color:{direction_colour}">{entry.direction}</span>',
            entry.protocol,
            entry.can_id,
            f'<code>{html.escape(entry.hex_data)}</code>',
            html.escape(entry.decoded_service or entry.message),
        ]
        return "<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>"

    def to_csv_row(self, entry: LogEntry) -> list[str]:
        """Return the CSV cells of *entry* in :attr:`CSV_COLUMNS` order."""
        mapping = entry.as_dict()
        return [str(mapping.get(column, "")) for column in self.CSV_COLUMNS]

    def csv_header(self) -> list[str]:
        """Return the CSV header row."""
        return list(self.CSV_COLUMNS)

    def html_document(self, entries: list[LogEntry], title: str = "Diagnostic log") -> str:
        """Render a complete styled HTML report."""
        rows = "\n".join(self.to_html_row(entry) for entry in entries)
        headers = "".join(
            f"<th>{name}</th>"
            for name in ("Time", "Level", "Category", "Dir", "Protocol", "ID", "Data", "Decoded")
        )
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
  body {{ background:#1E1E2E; color:#F8FAFC; font-family:'Roboto',sans-serif; padding:24px; }}
  h1 {{ font-size:20px; margin-bottom:16px; }}
  table {{ border-collapse:collapse; width:100%; font-size:13px; }}
  th {{ background:#282840; text-align:left; padding:8px; position:sticky; top:0; }}
  td {{ border-bottom:1px solid #374151; padding:6px 8px; vertical-align:top; }}
  code {{ font-family:'Roboto Mono',monospace; color:#94A3B8; }}
  tr:hover td {{ background:#282840; }}
</style>
</head>
<body>
<h1>{html.escape(title)} - {len(entries)} entries</h1>
<table><thead><tr>{headers}</tr></thead>
<tbody>
{rows}
</tbody></table>
</body>
</html>
"""


__all__ = ["LogFormatter", "FormatOptions", "LEVEL_COLORS", "DIRECTION_COLORS"]
