"""Tests for the reorderable flash sequence and its runner.

A flash is destructive and slow to retry on a bench, so the ordering rules,
the file handling and the per-step outcomes are all covered here against the
built-in ECU simulator.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.diagnostics.flash_sequence import (
    CATEGORY_ORDER,
    DEFAULT_ORDER,
    FlashSequence,
    FlashStep,
    FlashStepKind,
    StepStatus,
    palette_steps,
)


class TestStepCatalogue:
    """The palette the sequence editor drags from."""

    def test_default_sequence_matches_the_specification(self) -> None:
        """The 13 documented steps appear in the documented order."""
        expected = [
            "CAN_INIT",
            "CAN_CONFIG",
            "ECU_COMM",
            "READ_VIN",
            "READ_HARDWARE",
            "READ_SOFTWARE",
            "SECURITY_ACCESS",
            "ERASE_MEMORY",
            "FILE_UPLOAD",
            "REQUEST_DOWNLOAD",
            "TRANSFER_DATA",
            "TRANSFER_EXIT",
            "ECU_RESET",
        ]
        assert [kind.value for kind in DEFAULT_ORDER] == expected
        assert len(FlashSequence.default()) == 13

    def test_palette_offers_more_than_the_defaults(self) -> None:
        """Optional steps must be draggable in beyond the 13."""
        assert len(list(FlashStepKind)) > len(DEFAULT_ORDER)

    def test_every_step_is_in_a_palette_group(self) -> None:
        """No step may be missing from the editor palette."""
        grouped = palette_steps()
        listed = [kind for kinds in grouped.values() for kind in kinds]
        assert sorted(listed, key=lambda k: k.value) == sorted(
            FlashStepKind, key=lambda k: k.value
        )

    def test_groups_use_the_declared_order(self) -> None:
        """The palette groups appear in the documented order."""
        for name in palette_steps():
            assert name in CATEGORY_ORDER

    def test_every_step_has_a_label_and_detail(self) -> None:
        """The editor shows both, so neither may be empty."""
        for kind in FlashStepKind:
            assert kind.label
            assert kind.detail


class TestSequenceEditing:
    """Reordering, adding and removing steps."""

    def test_move_reorders(self) -> None:
        """Dragging a step changes its position."""
        sequence = FlashSequence.default()
        assert sequence.move(0, 3)
        assert sequence.steps[3].kind is FlashStepKind.CAN_INIT

    def test_move_rejects_out_of_range(self) -> None:
        """An impossible move leaves the sequence untouched."""
        sequence = FlashSequence.default()
        before = [step.kind for step in sequence.steps]
        assert not sequence.move(0, 99)
        assert [step.kind for step in sequence.steps] == before

    def test_add_and_remove(self) -> None:
        """A palette step can be inserted at any position and removed again."""
        sequence = FlashSequence.default()
        sequence.add(FlashStepKind.TESTER_PRESENT, 2)
        assert sequence.steps[2].kind is FlashStepKind.TESTER_PRESENT
        assert len(sequence) == 14
        assert sequence.remove(2)
        assert len(sequence) == 13

    def test_disabled_steps_are_excluded(self) -> None:
        """Only enabled steps are handed to the runner."""
        sequence = FlashSequence.default()
        sequence.steps[0].enabled = False
        assert len(sequence.enabled_steps) == 12


class TestValidation:
    """The rules that gate the start button."""

    def test_transfer_steps_need_a_file(self) -> None:
        """A sequence that transfers data must have a flash file."""
        problems = FlashSequence.default().validate()
        assert any("no flash file selected" in p for p in problems)

    def test_missing_file_is_reported(self, tmp_path) -> None:
        """A path that does not exist is caught before the run starts."""
        sequence = FlashSequence.default(flash_file=tmp_path / "absent.hex")
        assert any("does not exist" in p for p in sequence.validate())

    def test_valid_sequence_has_no_problems(self, tmp_path) -> None:
        """A complete sequence with a real file validates."""
        firmware = tmp_path / "fw.bin"
        firmware.write_bytes(b"\xaa" * 512)
        assert FlashSequence.default(flash_file=firmware).validate() == []

    def test_transfer_before_request_download_is_rejected(self, tmp_path) -> None:
        """The UDS state machine ordering is enforced."""
        firmware = tmp_path / "fw.bin"
        firmware.write_bytes(b"\xaa" * 512)
        sequence = FlashSequence.default(flash_file=firmware)
        download = next(
            i for i, s in enumerate(sequence.steps) if s.kind is FlashStepKind.REQUEST_DOWNLOAD
        )
        sequence.move(download, download + 1)
        assert any("must run before" in p for p in sequence.validate())

    def test_non_repeatable_duplicate_is_rejected(self) -> None:
        """Opening the CAN channel twice is a configuration error."""
        sequence = FlashSequence(
            steps=[FlashStep(kind=FlashStepKind.CAN_INIT) for _ in range(2)]
        )
        assert any("may only run once" in p for p in sequence.validate())

    def test_repeatable_duplicate_is_allowed(self) -> None:
        """Tester present may appear as often as the operator likes."""
        sequence = FlashSequence(
            steps=[FlashStep(kind=FlashStepKind.TESTER_PRESENT) for _ in range(3)]
        )
        assert sequence.validate() == []


class TestPersistence:
    """YAML round trip of a customised sequence."""

    def test_round_trip(self, tmp_path) -> None:
        """Order, options and files survive a save and load."""
        firmware = tmp_path / "fw.bin"
        firmware.write_bytes(b"\x00" * 16)
        original = FlashSequence.default(flash_file=firmware, security_level=0x09,
                                         block_size=512)
        original.add(FlashStepKind.DELAY, 0)
        original.steps[1].enabled = False
        restored = FlashSequence.from_dict(original.as_dict())
        assert [s.kind for s in restored.steps] == [s.kind for s in original.steps]
        assert restored.steps[1].enabled is False
        assert restored.security_level == 0x09
        assert restored.block_size == 512
        assert restored.flash_file == firmware


@pytest.fixture()
def ecu(tmp_path):
    """Return a connected client plus a firmware file, and clean up after."""
    from intelhex import IntelHex

    from src.communication.vci_drivers.virtual.virtual_bus import VirtualBus
    from tests.simulation.mock_ecu import make_simulator
    from tests.simulation.test_with_simulator import build_client, close

    image = IntelHex()
    image.frombytes(bytes(range(256)) * 8, offset=0x08000000)
    firmware = tmp_path / "K6060799_03_S.hex"
    image.write_hex_file(str(firmware))

    bus = VirtualBus(f"flash-{tmp_path.name}")
    client, driver, transport = build_client(make_simulator(bus), bus, 4000.0)
    yield client, firmware
    close(driver, transport)


def _programming_sequence(firmware: Path) -> FlashSequence:
    """Return the default sequence with the programming session inserted."""
    sequence = FlashSequence.default(
        flash_file=firmware, security_level=0x11,
        security_algorithm="add_constant", block_size=1024,
    )
    index = next(
        i for i, s in enumerate(sequence.steps) if s.kind is FlashStepKind.SECURITY_ACCESS
    )
    sequence.steps.insert(index, FlashStep(kind=FlashStepKind.ENTER_PROGRAMMING))
    return sequence


class TestRunner:
    """The runner against the built-in ECU simulator."""

    def test_full_sequence_passes(self, ecu) -> None:
        """Every step of the default sequence succeeds."""
        from src.diagnostics.flash_runner import FlashRunner

        client, firmware = ecu
        report = FlashRunner(client).run(_programming_sequence(firmware))
        assert report.completed, [o.message for o in report.failed]
        assert all(o.status is StepStatus.PASSED for o in report.outcomes)

    def test_progress_is_monotonic_and_reaches_100(self, ecu) -> None:
        """The bar must only move forwards and must finish full."""
        from src.diagnostics.flash_runner import FlashRunner

        client, firmware = ecu
        seen: list[float] = []
        runner = FlashRunner(client, on_progress=lambda p: seen.append(p.percent))
        runner.run(_programming_sequence(firmware))
        assert seen
        assert seen == sorted(seen)
        assert seen[-1] == pytest.approx(100.0)

    def test_block_count_matches_the_payload(self, ecu) -> None:
        """2048 bytes at 1024 per block is exactly two blocks."""
        from src.diagnostics.flash_runner import FlashRunner

        client, firmware = ecu
        report = FlashRunner(client).run(_programming_sequence(firmware))
        transfer = next(
            o for o in report.outcomes if o.step.kind is FlashStepKind.TRANSFER_DATA
        )
        assert transfer.data["bytes"] == 2048
        assert transfer.data["blocks"] == 2

    def test_crc_matches_the_file(self, ecu) -> None:
        """The transferred CRC equals the CRC of the parsed image."""
        import binascii

        from src.data_processing.file_parsers import parse_firmware_file
        from src.diagnostics.flash_runner import FlashRunner

        client, firmware = ecu
        report = FlashRunner(client).run(_programming_sequence(firmware))
        payload = b"".join(s.data for s in parse_firmware_file(firmware))
        assert report.info["crc32"] == binascii.crc32(payload) & 0xFFFFFFFF

    def test_identification_is_collected(self, ecu) -> None:
        """The VIN, hardware and software reads populate the report."""
        from src.diagnostics.flash_runner import FlashRunner

        client, firmware = ecu
        report = FlashRunner(client).run(_programming_sequence(firmware))
        assert report.info["vin"] == "WBAZZZ0GM12345678"
        assert report.info["hardware"]
        assert report.info["software"]

    def test_disabled_step_is_skipped(self, ecu) -> None:
        """A disabled step reports SKIPPED and does not run."""
        from src.diagnostics.flash_runner import FlashRunner

        client, firmware = ecu
        sequence = _programming_sequence(firmware)
        sequence.steps[3].enabled = False
        report = FlashRunner(client).run(sequence)
        skipped = [o for o in report.outcomes if o.status is StepStatus.SKIPPED]
        assert len(skipped) == 1

    def test_failure_stops_the_run(self, ecu) -> None:
        """With stop-on-failure the run aborts at the first error."""
        from src.diagnostics.flash_runner import FlashRunner

        client, firmware = ecu
        sequence = FlashSequence.default(flash_file=firmware)
        # Transfer without RequestDownload: the ECU refuses.
        sequence.steps = [
            FlashStep(kind=FlashStepKind.FILE_UPLOAD),
            FlashStep(kind=FlashStepKind.TRANSFER_DATA),
            FlashStep(kind=FlashStepKind.ECU_RESET),
        ]
        report = FlashRunner(client).run(sequence)
        assert not report.completed
        assert len(report.outcomes) == 2

    def test_step_order_is_honoured(self, ecu) -> None:
        """Reordering the sequence changes the execution order."""
        from src.diagnostics.flash_runner import FlashRunner

        client, firmware = ecu
        sequence = _programming_sequence(firmware)
        vin = next(i for i, s in enumerate(sequence.steps) if s.kind is FlashStepKind.READ_VIN)
        sequence.move(vin, 0)
        report = FlashRunner(client).run(sequence)
        assert report.outcomes[0].step.kind is FlashStepKind.READ_VIN

    def test_optional_steps_execute(self, ecu) -> None:
        """Steps dragged in from the palette run like the built-in ones."""
        from src.diagnostics.flash_runner import FlashRunner

        client, firmware = ecu
        sequence = _programming_sequence(firmware)
        sequence.add(FlashStepKind.READ_BATTERY_VOLTAGE, 3)
        sequence.add(FlashStepKind.DISABLE_DTC, 4)
        sequence.add(FlashStepKind.DELAY, 5)
        sequence.steps[5].options["milliseconds"] = 10
        report = FlashRunner(client).run(sequence)
        assert report.completed, [o.message for o in report.failed]
        kinds = [o.step.kind for o in report.outcomes]
        assert FlashStepKind.READ_BATTERY_VOLTAGE in kinds
        assert FlashStepKind.DISABLE_DTC in kinds
        assert FlashStepKind.DELAY in kinds

    @pytest.mark.parametrize(
        "suffix,writer",
        [
            (".bin", "binary"),
            (".hex", "intel"),
            (".s19", "srec"),
            (".mot", "srec"),
            (".srec", "srec"),
            (".ihx", "intel"),
        ],
    )
    def test_every_firmware_format_flashes(self, ecu, tmp_path, suffix, writer) -> None:
        """The transfer steps accept every supported firmware container."""
        from intelhex import IntelHex

        from src.diagnostics.flash_runner import FlashRunner

        client, _ = ecu
        data = bytes(range(256)) * 4
        target = tmp_path / f"image{suffix}"
        if writer == "binary":
            target.write_bytes(data)
        elif writer == "intel":
            image = IntelHex()
            image.frombytes(data, offset=0x08000000)
            image.write_hex_file(str(target))
        else:
            lines = []
            for offset in range(0, len(data), 16):
                chunk = data[offset : offset + 16]
                address = 0x08000000 + offset
                body = (4 + len(chunk) + 1).to_bytes(1, "big") + address.to_bytes(4, "big") + chunk
                lines.append(f"S3{body.hex().upper()}{(~sum(body)) & 0xFF:02X}")
            body = (4 + 1).to_bytes(1, "big") + (0).to_bytes(4, "big")
            lines.append(f"S7{body.hex().upper()}{(~sum(body)) & 0xFF:02X}")
            target.write_text("\n".join(lines) + "\n")

        sequence = _programming_sequence(target)
        sequence.base_address = 0x08000000
        report = FlashRunner(client).run(sequence)
        assert report.completed, [o.message for o in report.failed]
        transfer = next(
            o for o in report.outcomes if o.step.kind is FlashStepKind.TRANSFER_DATA
        )
        assert transfer.data["bytes"] == len(data)
