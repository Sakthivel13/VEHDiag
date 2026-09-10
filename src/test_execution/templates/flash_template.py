"""Template: complete flash sequence for one firmware file."""
from __future__ import annotations

#: Firmware file to download; set an absolute path before running.
FIRMWARE_PATH = ""

#: Address used when the firmware is a raw binary.
BASE_ADDRESS = 0x08000000

#: Security level of the programming session.
PROGRAMMING_LEVEL = 0x11

#: Seed-key algorithm matching the bootloader.
ALGORITHM = "add_constant"


class TestScript:
    """Drive session, security, download, verification and reset."""

    name = "Flash ECU"

    def __init__(self, api):
        """Store the diagnostic API."""
        self.api = api

    def setup(self):
        """Prepare the ECU: extended session, DTCs off, communication off."""
        self.api.change_session(0x03)
        self.api.send_hex("85 02")      # ControlDTCSetting off
        self.api.send_hex("28 03 01")   # CommunicationControl disable normal

    def execute(self):
        """Enter the programming session and transfer the firmware."""
        from pathlib import Path

        from src.data_processing.file_parsers import parse_firmware_file
        from src.diagnostics.services.transfer_services.transfer_manager import TransferManager

        if not FIRMWARE_PATH or not Path(FIRMWARE_PATH).is_file():
            self.api.log("set FIRMWARE_PATH to an existing firmware file")
            return "FAIL"

        if not self.api.change_session(0x02):
            self.api.log("the ECU refused the programming session")
            return "FAIL"
        if not self.api.security_unlock(PROGRAMMING_LEVEL, ALGORITHM):
            self.api.log("the security unlock for programming failed")
            return "FAIL"

        segments = parse_firmware_file(FIRMWARE_PATH, base_address=BASE_ADDRESS)
        self.api.log(f"{len(segments)} segment(s), {sum(s.size for s in segments)} bytes")

        manager = TransferManager(self.api.client)
        for report in manager.download_segments(segments):
            self.api.log(report.summary())
            if not report.successful:
                return "FAIL"
        return "PASS"

    def teardown(self):
        """Reset the ECU and restore normal communication."""
        self.api.ecu_reset(0x01)
        self.api.wait(1000)
        self.api.change_session(0x03)
        self.api.send_hex("28 00 01")   # enable communication
        self.api.send_hex("85 01")      # enable DTC setting
        self.api.change_session(0x01)
