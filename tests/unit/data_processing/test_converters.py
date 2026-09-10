"""Unit tests for the data converters and the response slicer."""
from __future__ import annotations

import pytest

from src.core.enums.data_format_enums import ByteOrder, DataFormat
from src.data_processing.converters.bcd_converter import BCDConverter
from src.data_processing.converters.custom_formula_converter import CustomFormulaConverter
from src.data_processing.converters.ieee754_converter import IEEE754Converter
from src.data_processing.converters.intel_converter import IntelConverter
from src.data_processing.converters.motorola_converter import MotorolaConverter
from src.data_processing.converters.physical_value_converter import (
    PhysicalValueConverter,
    ScalingRule,
)
from src.data_processing.data_converter import DataConverter
from src.data_processing.response_slicer import (
    ResponseSlicer,
    SliceDefinition,
    SliceProfile,
)


class TestDataConverter:
    """The master converter."""

    def test_convert_all_formats(self) -> None:
        """Every representation is produced at once."""
        result = DataConverter().convert_all(b"ABCD")
        assert result["HEX"] == "41 42 43 44"
        assert result["ASCII"] == "ABCD"
        assert result["DEC_UNSIGNED_BE"] == 0x41424344
        assert result["DEC_UNSIGNED_LE"] == 0x44434241
        assert result["UINT16_BE"] == [0x4142, 0x4344]
        assert result["BIN"].startswith("01000001")

    def test_empty_input(self) -> None:
        """Converting nothing yields an empty result."""
        assert DataConverter().convert_all(b"").values == {}

    @pytest.mark.parametrize(
        ("text", "fmt", "expected"),
        [
            ("41 42", DataFormat.HEX, b"AB"),
            ("AB", DataFormat.ASCII, b"AB"),
            ("01000001", DataFormat.BIN, b"\x41"),
            ("256", DataFormat.DEC_UNSIGNED, b"\x01\x00"),
        ],
    )
    def test_parse(self, text: str, fmt: DataFormat, expected: bytes) -> None:
        """Text in any format parses into bytes."""
        assert DataConverter().parse(text, fmt) == expected

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("01000001", DataFormat.BIN),
            ("0x4142", DataFormat.HEX),
            ("1234", DataFormat.DEC_UNSIGNED),
            ("hello world", DataFormat.ASCII),
        ],
    )
    def test_format_detection(self, text: str, expected: DataFormat) -> None:
        """The format of typical inputs is guessed correctly."""
        assert DataConverter.detect_format(text) is expected

    def test_physical_value(self) -> None:
        """A scaling rule produces the physical value."""
        result = DataConverter().convert_all(b"\x33\x90", ScalingRule(0.001, 0.0, "V"))
        assert result.physical == pytest.approx(13.2, abs=0.001)
        assert result.unit == "V"


class TestByteOrder:
    """Motorola and Intel interpretations."""

    def test_motorola_is_big_endian(self) -> None:
        """Motorola reads the most significant byte first."""
        assert MotorolaConverter().convert(b"\x01\x00") == 256

    def test_intel_is_little_endian(self) -> None:
        """Intel reads the least significant byte first."""
        assert IntelConverter().convert(b"\x01\x00") == 1

    def test_motorola_signal_extraction(self) -> None:
        """Motorola bit numbering is translated correctly."""
        assert MotorolaConverter().extract_signal(b"\xf0\x00", 7, 4) == 0x0F

    def test_intel_signal_extraction(self) -> None:
        """Intel bit numbering starts at the least significant bit."""
        assert IntelConverter().extract_signal(b"\x0f\x00", 0, 4) == 0x0F

    def test_signed_signals(self) -> None:
        """Signed extraction applies the two's complement."""
        assert IntelConverter().extract_signal(b"\xff", 0, 8, signed=True) == -1


class TestFloatAndBCD:
    """IEEE-754 and BCD conversion."""

    def test_float32(self) -> None:
        """A float32 round trips."""
        converter = IEEE754Converter()
        data = converter.to_bytes(3.14159265, width=4)
        assert converter.convert(data) == pytest.approx(3.14159, abs=1e-5)

    def test_float64(self) -> None:
        """A float64 round trips."""
        converter = IEEE754Converter()
        data = converter.to_bytes(3.14159265358979, width=8)
        assert converter.convert(data) == pytest.approx(3.14159265358979)

    def test_invalid_length(self) -> None:
        """Only four or eight bytes are accepted."""
        with pytest.raises(ValueError):
            IEEE754Converter().convert(b"\x01\x02\x03")

    def test_bcd_round_trip(self) -> None:
        """Packed BCD converts back and forth."""
        converter = BCDConverter()
        assert converter.convert(b"\x12\x34") == 1234
        assert converter.to_bytes(1234) == b"\x12\x34"

    def test_bcd_validation(self) -> None:
        """Invalid nibbles are rejected."""
        with pytest.raises(ValueError):
            BCDConverter().convert(b"\x1a")

    def test_bcd_date(self) -> None:
        """A manufacturing date is formatted as ISO."""
        assert BCDConverter().to_date(b"\x20\x24\x01\x15") == "2024-01-15"


class TestPhysicalAndFormula:
    """Physical scaling and custom formulas."""

    def test_scaling(self) -> None:
        """Factor and offset are applied."""
        rule = ScalingRule(0.1, -40.0, "degC")
        assert PhysicalValueConverter(rule).convert(b"\xc8") == pytest.approx(-20.0)

    def test_clamping(self) -> None:
        """The value is clamped to the configured range."""
        rule = ScalingRule(1.0, 0.0, "", minimum=0.0, maximum=100.0)
        assert PhysicalValueConverter(rule).convert(b"\xff") == 100.0

    def test_inverse(self) -> None:
        """The raw value can be recovered from the physical one."""
        rule = ScalingRule(0.5, 10.0)
        assert rule.invert(rule.apply(40)) == pytest.approx(40)

    def test_custom_formula(self) -> None:
        """A user formula is evaluated safely."""
        assert CustomFormulaConverter("raw * 0.1 - 40").convert(b"\xc8") == pytest.approx(-20.0)

    def test_formula_rejects_imports(self) -> None:
        """Dangerous expressions cannot be evaluated."""
        with pytest.raises(ValueError):
            CustomFormulaConverter("__import__('os').system('ls')").convert(b"\x00")


class TestResponseSlicer:
    """Byte and bit slicing."""

    def test_slice_bytes(self) -> None:
        """A byte range is extracted."""
        assert ResponseSlicer.slice_bytes(bytes.fromhex("62F19041"), 1, 2) == b"\xf1\x90"

    def test_slice_beyond_end(self) -> None:
        """Out of range requests return what is available."""
        assert ResponseSlicer.slice_bytes(b"\x01\x02", 1, 10) == b"\x02"

    def test_slice_bits(self) -> None:
        """Bit ranges are extracted MSB first."""
        assert ResponseSlicer.slice_bits(bytes([0b10110000]), 0, 4) == 0b1011

    def test_profile_application(self) -> None:
        """A profile converts each slice with its own format."""
        data = bytes.fromhex("62F190") + b"WBAZ"
        profile = SliceProfile("test")
        profile.add(SliceDefinition("SID", 0, 1))
        profile.add(SliceDefinition("DID", 1, 2))
        profile.add(SliceDefinition("VIN", 3, 4, data_format=DataFormat.ASCII))
        values = ResponseSlicer().apply_dict(data, profile)
        assert values == {"SID": "62", "DID": "F1 90", "VIN": "WBAZ"}

    def test_physical_slice(self) -> None:
        """A slice can produce a physical value."""
        profile = SliceProfile("voltage")
        profile.add(
            SliceDefinition("Battery", 0, 2, data_format=DataFormat.PHYSICAL,
                            factor=0.001, unit="V")
        )
        results = ResponseSlicer().apply(b"\x33\x90", profile)
        assert results[0].value == pytest.approx(13.2, abs=0.001)
        assert "V" in results[0].display

    def test_profile_persistence(self, tmp_path) -> None:
        """Profiles survive a save and load round trip."""
        profile = SliceProfile("saved")
        profile.add(SliceDefinition("first", 0, 2))
        path = profile.save(tmp_path / "profile.yaml")
        loaded = SliceProfile.load(path)
        assert loaded.name == "saved"
        assert loaded.slices[0].length == 2

    def test_auto_profile(self) -> None:
        """The auto profile recognises a ReadDataByIdentifier response."""
        profile = ResponseSlicer.auto_profile(bytes.fromhex("62F1904142"))
        assert [definition.name for definition in profile.slices] == [
            "Service echo",
            "Data identifier",
            "Data",
        ]

    def test_byte_map_colours(self) -> None:
        """Every byte reports the slice it belongs to."""
        profile = SliceProfile("map")
        profile.add(SliceDefinition("head", 0, 2))
        mapping = ResponseSlicer.byte_map(b"\x01\x02\x03", profile)
        assert mapping[0]["slice"] == "head"
        assert mapping[2]["slice"] == ""

    def test_error_is_reported(self) -> None:
        """A bad slice reports an error instead of raising."""
        profile = SliceProfile("bad")
        profile.add(SliceDefinition("missing", 10, 2))
        results = ResponseSlicer().apply(b"\x01", profile)
        assert results[0].error
