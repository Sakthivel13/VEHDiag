"""Template: blank starting point for a custom test."""
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
        """Prepare the ECU before the test runs."""
        self.api.change_session(0x03)

    def execute(self):
        """Run the test.

        Returns:
            ``"PASS"``, ``"FAIL"`` or a boolean; ``None`` counts as a pass.
        """
        # self.api.send_hex("22 F1 90")
        # self.api.assert_positive_response()
        # self.api.log(f"response: {self.api.get_last_response().hex_raw}")
        return "PASS"

    def teardown(self):
        """Restore the ECU state after the test."""
        self.api.change_session(0x01)
