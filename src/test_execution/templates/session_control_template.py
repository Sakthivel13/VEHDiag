"""Template: change the diagnostic session and verify the timing."""
from __future__ import annotations

#: Session this template requests.
TARGET_SESSION = 0x03


class TestScript:
    """Enter a diagnostic session and check the reported P2 timing."""

    name = "Session control"

    def __init__(self, api):
        """Store the diagnostic API."""
        self.api = api

    def setup(self):
        """Start from the default session."""
        self.api.change_session(0x01)

    def execute(self):
        """Request the target session and verify the response."""
        self.api.send_hex(f"10 {TARGET_SESSION:02X}")
        self.api.assert_positive_response("the ECU refused the session change")
        raw = self.api.get_last_response().raw
        self.api.assert_equal(raw[1], TARGET_SESSION, "the ECU echoed a different session")
        if len(raw) >= 6:
            p2 = int.from_bytes(raw[2:4], "big")
            p2_star = int.from_bytes(raw[4:6], "big") * 10
            self.api.log(f"P2 = {p2} ms, P2* = {p2_star} ms")
            self.api.set_variable("p2_ms", p2)
        return "PASS"

    def teardown(self):
        """Return to the default session."""
        self.api.change_session(0x01)
