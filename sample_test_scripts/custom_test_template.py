"""Template for a custom test script - copy and adapt."""
from __future__ import annotations


class TestScript:
    """Describe here what this test verifies."""

    #: Name shown in the developer mode results table.
    name = "Custom test"

    def __init__(self, api):
        """Store the diagnostic API handed in by the runner.

        Args:
            api: A ``DiagnosticAPI`` giving access to the ECU.
        """
        self.api = api

    def setup(self):
        """Prepare the ECU before the test runs.

        Typical steps: change the session, unlock security, disable DTCs.
        """
        self.api.change_session(0x03)

    def execute(self):
        """Run the test.

        Returns:
            ``"PASS"``, ``"FAIL"``, or a boolean; ``None`` counts as PASS.
        """
        self.api.send_hex("22 F1 90")
        self.api.assert_positive_response("the ECU did not return the VIN")
        vin = self.api.get_last_response().raw[3:].decode("ascii", errors="replace")
        self.api.log(f"VIN: {vin}")
        self.api.assert_equal(len(vin), 17, "a VIN must be 17 characters long")
        return "PASS"

    def teardown(self):
        """Restore the ECU state after the test."""
        self.api.change_session(0x01)
