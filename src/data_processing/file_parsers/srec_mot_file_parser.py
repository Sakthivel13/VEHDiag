"""Motorola S-Record parser (.s19, .s28, .s37, .mot, .srec)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ...core.exceptions import ChecksumMismatchError, ParseError
from ...core.models.file_transfer_model import MemorySegment
from .base_file_parser import BaseFileParser
from .memory_map import MemoryMap

_logger = logging.getLogger(__name__)

#: Address width in bytes for each data / termination record type.
ADDRESS_WIDTH: dict[int, int] = {0: 2, 1: 2, 2: 3, 3: 4, 5: 2, 6: 3, 7: 4, 8: 3, 9: 2}

#: Record types carrying payload data.
DATA_RECORDS = (1, 2, 3)

#: Record types terminating a file.
END_RECORDS = (7, 8, 9)


def srec_checksum(payload: bytes) -> int:
    """Return the S-Record checksum of *payload* (count + address + data).

    Example:
        >>> hex(srec_checksum(bytes.fromhex("0500000102")))
        '0xf7'
    """
    return (~sum(payload)) & 0xFF


class SRecordParser(BaseFileParser):
    """Parse and write Motorola S-Record files.

    Example:
        >>> import tempfile, pathlib
        >>> parser = SRecordParser()
        >>> line = parser.build_record(1, 0x1000, b"\\x01\\x02")
        >>> path = pathlib.Path(tempfile.mkstemp(suffix=".s19")[1])
        >>> _ = path.write_text(line + "\\n" + parser.build_record(9, 0, b"") + "\\n")
        >>> segments = parser.parse(path)
        >>> hex(segments[0].address), segments[0].data.hex()
        ('0x1000', '0102')
    """

    format_name = "Motorola S-Record"
    suffixes = (".s19", ".s28", ".s37", ".mot", ".srec", ".s1", ".s2", ".s3", ".sre")

    def parse(self, path: str | Path, **options: Any) -> list[MemorySegment]:
        """Parse an S-Record file into memory segments.

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
        current_address: int | None = None
        buffer = bytearray()
        self.header = ""
        self.entry_point = 0
        self.record_count = 0

        for number, line in enumerate(self._read_lines(path), start=1):
            if not line.upper().startswith("S") or len(line) < 4:
                continue
            try:
                record_type = int(line[1])
                body = bytes.fromhex(line[2:])
            except ValueError as exc:
                raise ParseError(f"invalid S-Record on line {number}") from exc
            if not body:
                raise ParseError(f"empty S-Record body on line {number}")
            count = body[0]
            if len(body) != count + 1:
                raise ParseError(
                    f"S-Record on line {number} declares {count} bytes but has {len(body) - 1}"
                )
            if verify and srec_checksum(body[:-1]) != body[-1]:
                raise ChecksumMismatchError(
                    f"S-Record checksum mismatch on line {number}",
                    {"expected": f"0x{srec_checksum(body[:-1]):02X}", "found": f"0x{body[-1]:02X}"},
                )
            width = ADDRESS_WIDTH.get(record_type, 2)
            address = int.from_bytes(body[1 : 1 + width], "big")
            data = body[1 + width : -1]

            if record_type == 0:
                self.header = data.decode("ascii", errors="replace").strip("\x00")
            elif record_type in DATA_RECORDS:
                if current_address is not None and address == current_address + len(buffer):
                    buffer.extend(data)
                else:
                    if buffer and current_address is not None:
                        segments.append(MemorySegment(current_address, bytes(buffer)))
                    current_address, buffer = address, bytearray(data)
            elif record_type == 5:
                self.record_count = address
            elif record_type in END_RECORDS:
                self.entry_point = address
                break

        if buffer and current_address is not None:
            segments.append(MemorySegment(current_address, bytes(buffer)))
        if options.get("merge_adjacent", True):
            memory = MemoryMap(self._sorted(segments))
            memory.merge_adjacent()
            return memory.segments
        return self._sorted(segments)

    def get_metadata(self, path: str | Path) -> dict[str, Any]:
        """Return the base metadata plus the S0 header and entry point."""
        metadata = super().get_metadata(path)
        metadata.update(
            {
                "header": getattr(self, "header", ""),
                "entry_point": getattr(self, "entry_point", 0),
                "record_count": getattr(self, "record_count", 0),
            }
        )
        return metadata

    @staticmethod
    def build_record(record_type: int, address: int, data: bytes) -> str:
        """Return one S-Record line.

        Example:
            >>> SRecordParser.build_record(9, 0, b"")
            'S9030000FC'
        """
        width = ADDRESS_WIDTH.get(record_type, 2)
        body = bytes([width + len(data) + 1]) + address.to_bytes(width, "big") + data
        return f"S{record_type}" + (body + bytes([srec_checksum(body)])).hex().upper()

    def write(
        self,
        path: str | Path,
        segments: list[MemorySegment],
        line_length: int = 16,
        header: str = "VDP",
    ) -> Path:
        """Write *segments* into an S-Record file using S3 data records."""
        lines = [self.build_record(0, 0, header.encode("ascii")[:32])]
        count = 0
        for segment in sorted(segments, key=lambda s: s.address):
            for offset in range(0, segment.size, line_length):
                lines.append(
                    self.build_record(
                        3, segment.address + offset, segment.data[offset : offset + line_length]
                    )
                )
                count += 1
        lines.append(self.build_record(5, count & 0xFFFF, b""))
        lines.append(self.build_record(7, 0, b""))
        target = Path(path).expanduser()
        target.write_text("\n".join(lines) + "\n", encoding="ascii")
        return target


#: Backwards compatible alias matching the module name in the blueprint.
SrecMotFileParser = SRecordParser

__all__ = ["SRecordParser", "SrecMotFileParser", "srec_checksum", "ADDRESS_WIDTH"]
