"""Intel HEX file parser."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Iterator

from ...core.exceptions import ChecksumMismatchError, ParseError
from ...core.models.file_transfer_model import MemorySegment
from ...utils.checksum_calculator import twos_complement_checksum
from .base_file_parser import BaseFileParser
from .memory_map import MemoryMap

_logger = logging.getLogger(__name__)

#: Intel HEX record types.
RECORD_DATA = 0x00
RECORD_EOF = 0x01
RECORD_EXTENDED_SEGMENT = 0x02
RECORD_START_SEGMENT = 0x03
RECORD_EXTENDED_LINEAR = 0x04
RECORD_START_LINEAR = 0x05


class HexFileParser(BaseFileParser):
    """Parse and write Intel HEX (``.hex``, ``.ihex``) files.

    Example:
        >>> import tempfile, pathlib
        >>> text = ":020000040800F2\\n:0400000001020304F2\\n:00000001FF\\n"
        >>> path = pathlib.Path(tempfile.mkstemp(suffix=".hex")[1])
        >>> _ = path.write_text(text)
        >>> segments = HexFileParser().parse(path)
        >>> hex(segments[0].address), segments[0].data.hex()
        ('0x8000000', '01020304')
    """

    format_name = "Intel HEX"
    suffixes = (".hex", ".ihex", ".ihx", ".h86")

    def parse(self, path: str | Path, **options: Any) -> list[MemorySegment]:
        """Parse an Intel HEX file into memory segments.

        Args:
            path: File to read.
            **options: ``verify_checksum`` (default ``True``) and
                ``merge_adjacent`` (default ``True``).

        Raises:
            ParseError: A record is malformed.
            ChecksumMismatchError: A record checksum is wrong.
        """
        verify = bool(options.get("verify_checksum", True))
        segments: list[MemorySegment] = []
        base_address = 0
        current_address: int | None = None
        buffer = bytearray()

        for number, line in enumerate(self._read_lines(path), start=1):
            if not line.startswith(":"):
                continue
            try:
                record = bytes.fromhex(line[1:])
            except ValueError as exc:
                raise ParseError(f"invalid hex characters on line {number}") from exc
            if len(record) < 5:
                raise ParseError(f"truncated record on line {number}")
            count, offset, record_type = record[0], int.from_bytes(record[1:3], "big"), record[3]
            data = record[4 : 4 + count]
            if len(data) != count:
                raise ParseError(f"record on line {number} declares {count} bytes but has {len(data)}")
            if verify and twos_complement_checksum(record[:-1]) != record[-1]:
                raise ChecksumMismatchError(
                    f"checksum mismatch on line {number}",
                    {"expected": f"0x{twos_complement_checksum(record[:-1]):02X}",
                     "found": f"0x{record[-1]:02X}"},
                )

            if record_type == RECORD_DATA:
                address = base_address + offset
                if current_address is not None and address == current_address + len(buffer):
                    buffer.extend(data)
                else:
                    if buffer and current_address is not None:
                        segments.append(MemorySegment(current_address, bytes(buffer)))
                    current_address, buffer = address, bytearray(data)
            elif record_type == RECORD_EXTENDED_LINEAR:
                if buffer and current_address is not None:
                    segments.append(MemorySegment(current_address, bytes(buffer)))
                    current_address, buffer = None, bytearray()
                base_address = int.from_bytes(data[:2], "big") << 16
            elif record_type == RECORD_EXTENDED_SEGMENT:
                if buffer and current_address is not None:
                    segments.append(MemorySegment(current_address, bytes(buffer)))
                    current_address, buffer = None, bytearray()
                base_address = int.from_bytes(data[:2], "big") << 4
            elif record_type == RECORD_EOF:
                break
            elif record_type in (RECORD_START_SEGMENT, RECORD_START_LINEAR):
                continue
            else:
                _logger.debug("ignoring unknown Intel HEX record type 0x%02X", record_type)

        if buffer and current_address is not None:
            segments.append(MemorySegment(current_address, bytes(buffer)))
        if options.get("merge_adjacent", True):
            memory = MemoryMap(self._sorted(segments))
            memory.merge_adjacent()
            return memory.segments
        return self._sorted(segments)

    def iter_records(self, path: str | Path) -> Iterator[tuple[int, int, bytes]]:
        """Yield ``(record_type, address, data)`` for every record."""
        base_address = 0
        for line in self._read_lines(path):
            if not line.startswith(":"):
                continue
            record = bytes.fromhex(line[1:])
            count, offset, record_type = record[0], int.from_bytes(record[1:3], "big"), record[3]
            data = record[4 : 4 + count]
            if record_type == RECORD_EXTENDED_LINEAR:
                base_address = int.from_bytes(data[:2], "big") << 16
            yield record_type, base_address + offset, data

    @staticmethod
    def build_record(record_type: int, offset: int, data: bytes) -> str:
        """Return one Intel HEX record line.

        Example:
            >>> HexFileParser.build_record(0x01, 0, b"")
            ':00000001FF'
        """
        body = bytes([len(data)]) + offset.to_bytes(2, "big") + bytes([record_type]) + data
        return ":" + (body + bytes([twos_complement_checksum(body)])).hex().upper()

    def write(self, path: str | Path, segments: list[MemorySegment], line_length: int = 16) -> Path:
        """Write *segments* back into an Intel HEX file."""
        lines: list[str] = []
        upper = -1
        for segment in sorted(segments, key=lambda s: s.address):
            for offset in range(0, segment.size, line_length):
                address = segment.address + offset
                chunk = segment.data[offset : offset + line_length]
                high = (address >> 16) & 0xFFFF
                if high != upper:
                    lines.append(self.build_record(RECORD_EXTENDED_LINEAR, 0, high.to_bytes(2, "big")))
                    upper = high
                lines.append(self.build_record(RECORD_DATA, address & 0xFFFF, chunk))
        lines.append(self.build_record(RECORD_EOF, 0, b""))
        target = Path(path).expanduser()
        target.write_text("\n".join(lines) + "\n", encoding="ascii")
        return target


__all__ = [
    "HexFileParser",
    "RECORD_DATA",
    "RECORD_EOF",
    "RECORD_EXTENDED_LINEAR",
    "RECORD_EXTENDED_SEGMENT",
]
