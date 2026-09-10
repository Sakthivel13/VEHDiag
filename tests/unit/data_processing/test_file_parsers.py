"""Unit tests for the firmware file parsers."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.core.exceptions import ChecksumMismatchError, FormatNotSupportedError, ParseError
from src.core.models.file_transfer_model import MemorySegment
from src.data_processing.file_parsers import (
    BinFileParser,
    FileMerger,
    FileValidator,
    HexFileParser,
    MemoryMap,
    SRecordParser,
    describe_firmware_file,
    parse_firmware_file,
)

#: Firmware image used across the tests.
PAYLOAD = bytes(i & 0xFF for i in range(1024))
BASE = 0x08000000


@pytest.fixture()
def segments() -> list[MemorySegment]:
    """Return a single segment covering the payload."""
    return [MemorySegment(BASE, PAYLOAD)]


class TestIntelHex:
    """Intel HEX parsing and writing."""

    def test_round_trip(self, tmp_path: Path, segments) -> None:
        """Writing and re-reading preserves the data."""
        path = HexFileParser().write(tmp_path / "image.hex", segments)
        parsed = HexFileParser().parse(path)
        assert parsed[0].address == BASE
        assert parsed[0].data == PAYLOAD

    def test_checksum_validation(self, tmp_path: Path) -> None:
        """A corrupted record is rejected."""
        path = tmp_path / "bad.hex"
        path.write_text(":0400000001020304FF\n:00000001FF\n")
        with pytest.raises(ChecksumMismatchError):
            HexFileParser().parse(path)

    def test_checksum_can_be_skipped(self, tmp_path: Path) -> None:
        """Validation is optional."""
        path = tmp_path / "bad.hex"
        path.write_text(":0400000001020304FF\n:00000001FF\n")
        assert HexFileParser().parse(path, verify_checksum=False)[0].data == b"\x01\x02\x03\x04"

    def test_extended_linear_address(self, tmp_path: Path) -> None:
        """The upper address word is applied."""
        parser = HexFileParser()
        lines = [
            parser.build_record(0x04, 0, b"\x08\x00"),
            parser.build_record(0x00, 0x1000, b"\xaa\xbb"),
            parser.build_record(0x01, 0, b""),
        ]
        path = tmp_path / "linear.hex"
        path.write_text("\n".join(lines))
        assert parser.parse(path)[0].address == 0x08001000

    def test_metadata(self, tmp_path: Path, segments) -> None:
        """The metadata reports the address range."""
        path = HexFileParser().write(tmp_path / "image.hex", segments)
        metadata = describe_firmware_file(path)
        assert metadata["format"] == "Intel HEX"
        assert metadata["data_size"] == len(PAYLOAD)
        assert metadata["start_address"] == BASE


class TestSRecord:
    """Motorola S-Record parsing and writing."""

    def test_round_trip(self, tmp_path: Path, segments) -> None:
        """Writing and re-reading preserves the data."""
        path = SRecordParser().write(tmp_path / "image.mot", segments)
        parsed = SRecordParser().parse(path)
        assert parsed[0].address == BASE
        assert parsed[0].data == PAYLOAD

    def test_header_and_entry_point(self, tmp_path: Path, segments) -> None:
        """The S0 header and the termination record are parsed."""
        parser = SRecordParser()
        path = parser.write(tmp_path / "image.s19", segments, header="TESTHDR")
        metadata = parser.get_metadata(path)
        assert metadata["header"] == "TESTHDR"
        assert metadata["record_count"] > 0

    def test_bad_checksum(self, tmp_path: Path) -> None:
        """A corrupted record is rejected."""
        path = tmp_path / "bad.s19"
        path.write_text("S1050000010200\n")
        with pytest.raises(ChecksumMismatchError):
            SRecordParser().parse(path)

    @pytest.mark.parametrize("suffix", [".s19", ".s28", ".s37", ".mot", ".srec"])
    def test_suffixes(self, tmp_path: Path, segments, suffix: str) -> None:
        """Every S-Record suffix is recognised."""
        path = SRecordParser().write(tmp_path / f"image{suffix}", segments)
        assert parse_firmware_file(path)[0].data == PAYLOAD


class TestBinary:
    """Raw binary parsing."""

    def test_base_address(self, tmp_path: Path) -> None:
        """The base address is applied to the single segment."""
        path = tmp_path / "image.bin"
        path.write_bytes(PAYLOAD)
        segment = BinFileParser().parse(path, base_address=BASE)[0]
        assert segment.address == BASE
        assert segment.data == PAYLOAD

    def test_block_splitting(self, tmp_path: Path) -> None:
        """A block size splits the image into several segments."""
        path = tmp_path / "image.bin"
        path.write_bytes(PAYLOAD)
        blocks = BinFileParser().parse(path, base_address=BASE, block_size=256)
        assert len(blocks) == 4
        assert blocks[1].address == BASE + 256

    def test_empty_file(self, tmp_path: Path) -> None:
        """An empty file raises."""
        from src.core.exceptions import EmptyFileError

        path = tmp_path / "empty.bin"
        path.write_bytes(b"")
        with pytest.raises(EmptyFileError):
            BinFileParser().parse(path)

    def test_streaming(self, tmp_path: Path) -> None:
        """Large files can be streamed block by block."""
        path = tmp_path / "image.bin"
        path.write_bytes(PAYLOAD)
        blocks = list(BinFileParser().iter_blocks(path, 128))
        assert len(blocks) == 8
        assert b"".join(blocks) == PAYLOAD


class TestMemoryMap:
    """Memory map operations."""

    def test_merge_adjacent(self) -> None:
        """Adjacent segments become one."""
        memory = MemoryMap([MemorySegment(0x100, b"\x01"), MemorySegment(0x101, b"\x02")])
        memory.merge_adjacent()
        assert len(memory) == 1
        assert memory.segments[0].data == b"\x01\x02"

    def test_gaps(self) -> None:
        """Holes between segments are reported."""
        memory = MemoryMap([MemorySegment(0x100, b"\x01"), MemorySegment(0x200, b"\x02")])
        gaps = memory.gaps()
        assert len(gaps) == 1
        assert gaps[0].size == 0xFF

    def test_fill_gaps(self) -> None:
        """Gaps can be filled with a pattern."""
        memory = MemoryMap([MemorySegment(0x00, b"\x01"), MemorySegment(0x04, b"\x02")])
        memory.fill_gaps(0xFF)
        assert len(memory) == 1
        assert memory.total_size == 5

    def test_read_with_fill(self) -> None:
        """Reading across a gap inserts the fill byte."""
        memory = MemoryMap([MemorySegment(0x00, b"\x01"), MemorySegment(0x02, b"\x03")])
        assert memory.read(0x00, 3, fill=0xEE) == b"\x01\xee\x03"

    def test_split(self) -> None:
        """A map splits into transfer blocks."""
        memory = MemoryMap([MemorySegment(0, PAYLOAD)])
        assert len(memory.split(256)) == 4

    def test_layout_rows(self) -> None:
        """The layout rows describe every segment."""
        memory = MemoryMap([MemorySegment(BASE, PAYLOAD)])
        rows = memory.layout_rows()
        assert rows[0]["start"] == "0x08000000"
        assert rows[0]["size"] == len(PAYLOAD)


class TestMergerAndValidator:
    """Merging and validation."""

    def test_merge_files(self, tmp_path: Path) -> None:
        """Files of different formats merge into one map."""
        HexFileParser().write(tmp_path / "a.hex", [MemorySegment(0x1000, b"\x01\x02")])
        SRecordParser().write(tmp_path / "b.mot", [MemorySegment(0x2000, b"\x03\x04")])
        memory, report = FileMerger().merge_files([tmp_path / "a.hex", tmp_path / "b.mot"])
        assert memory.total_size == 4
        assert report.segments_out == 2
        assert not report.overlaps

    def test_overlap_detection(self) -> None:
        """Overlapping segments are reported."""
        merger = FileMerger()
        _memory, report = merger.merge_segments(
            [MemorySegment(0x00, b"\x01\x02\x03"), MemorySegment(0x01, b"\xff")]
        )
        assert report.overlaps

    def test_overlap_rejection(self) -> None:
        """The reject policy raises on overlap."""
        from src.data_processing.file_parsers.file_merger import OverlapPolicy

        merger = FileMerger(OverlapPolicy.REJECT)
        with pytest.raises(ParseError):
            merger.merge_segments(
                [MemorySegment(0x00, b"\x01\x02"), MemorySegment(0x01, b"\xff")]
            )

    def test_validator_checksums(self) -> None:
        """The validator computes the standard digests."""
        result = FileValidator().validate_bytes(b"12345")
        assert result.valid
        assert result.checksums["CRC32"] == 0xCBF53A1C

    def test_validator_detects_mismatch(self) -> None:
        """A wrong expected digest fails the validation."""
        result = FileValidator().validate_bytes(b"12345", expected={"CRC32": 0x12345678})
        assert not result.valid
        assert "CRC32 mismatch" in result.problems[0]

    def test_validator_size_check(self) -> None:
        """The size is validated as well."""
        result = FileValidator().validate_bytes(b"12345", expected_size=10)
        assert not result.valid

    def test_unsupported_format(self, tmp_path: Path) -> None:
        """An unknown suffix raises."""
        path = tmp_path / "image.xyz"
        path.write_bytes(b"\x00")
        with pytest.raises(FormatNotSupportedError):
            parse_firmware_file(path)
