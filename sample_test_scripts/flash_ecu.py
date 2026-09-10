"""Complete flash sequence: session, security, download, verify, reset."""
from __future__ import annotations

#: Memory address the firmware is written to.
TARGET_ADDRESS = 0x08000000
#: Demo payload; replace with a parsed firmware file in production.
DEMO_PAYLOAD = bytes(range(256)) * 4


class TestScript:
    """Drive a full programming sequence against the ECU."""

    name = "Flash ECU"

    def __init__(self, api):
        """Store the diagnostic API."""
        self.api = api

    def setup(self):
        """Prepare the ECU: extended session, DTCs off, communication off."""
        self.api.change_session(0x03)
        self.api.send_hex("85 02")  # ControlDTCSetting off
        self.api.send_hex("28 03 01")  # CommunicationControl disable normal

    def execute(self):
        """Enter the programming session and download the payload."""
        from src.diagnostics.services.transfer_services.transfer_manager import TransferManager

        if not self.api.change_session(0x02):
            self.api.log("the ECU refused the programming session")
            return "FAIL"
        if not self.api.security_unlock(0x11, "add_constant"):
            self.api.log("security unlock for programming failed")
            return "FAIL"

        manager = TransferManager(self.api.client)
        report = manager.download(TARGET_ADDRESS, DEMO_PAYLOAD)
        self.api.log(report.summary())
        if not report.successful:
            return "FAIL"
        self.api.log(f"CRC-32 of the transferred image: 0x{report.crc32:08X}")
        return "PASS"

    def teardown(self):
        """Reset the ECU and restore normal communication."""
        self.api.ecu_reset(0x01)
        self.api.wait(500)
        self.api.change_session(0x03)
        self.api.send_hex("28 00 01")
        self.api.send_hex("85 01")
        self.api.change_session(0x01)
