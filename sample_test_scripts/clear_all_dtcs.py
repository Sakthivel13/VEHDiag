"""Clear every DTC and verify the memory is empty afterwards."""
from __future__ import annotations


class TestScript:
    """Clear all diagnostic trouble codes and confirm the result."""

    name = "Clear all DTCs"

    def __init__(self, api):
        """Store the diagnostic API."""
        self.api = api

    def setup(self):
        """Enter the extended diagnostic session."""
        self.api.change_session(0x03)

    def execute(self):
        """Clear the DTCs and verify none remain."""
        before = self.api.read_dtcs(0xFF)
        self.api.log(f"{len(before)} DTC(s) before clearing")
        if not self.api.clear_dtcs(0xFFFFFF):
            return "FAIL"
        self.api.wait(200)
        after = self.api.read_dtcs(0xFF)
        self.api.log(f"{len(after)} DTC(s) after clearing")
        return "PASS" if not after else "FAIL"

    def teardown(self):
        """Nothing to clean up."""
