"""Template: clear the fault memory and verify it stays empty."""
from __future__ import annotations

#: Group to clear; 0xFFFFFF clears everything.
GROUP = 0xFFFFFF

#: Time the ECU is given to finish the operation, in milliseconds.
SETTLE_MS = 300


class TestScript:
    """Clear every DTC and confirm the memory is empty afterwards."""

    name = "Clear DTCs"

    def __init__(self, api):
        """Store the diagnostic API."""
        self.api = api

    def setup(self):
        """Enter the extended session."""
        self.api.change_session(0x03)

    def execute(self):
        """Clear the memory and verify the result."""
        before = self.api.read_dtcs(0xFF)
        self.api.log(f"{len(before)} DTC(s) before clearing")
        if not self.api.clear_dtcs(GROUP):
            self.api.log("the ECU rejected the clear request")
            return "FAIL"
        self.api.wait(SETTLE_MS)
        after = self.api.read_dtcs(0xFF)
        self.api.log(f"{len(after)} DTC(s) after clearing")
        return "PASS" if not after else "FAIL"

    def teardown(self):
        """Nothing to clean up."""
