"""End-of-line verification: identification, DTC check, clear and reset."""
from __future__ import annotations

#: DIDs that must be readable for the ECU to pass the end-of-line test.
REQUIRED_DIDS: tuple[int, ...] = (0xF190, 0xF18C)


class TestScript:
    """Production line acceptance test."""

    name = "End of line test"

    def __init__(self, api):
        """Store the diagnostic API."""
        self.api = api
        self.failures: list[str] = []

    def setup(self):
        """Enter the extended diagnostic session."""
        self.api.change_session(0x03)

    def execute(self):
        """Verify identification, clear DTCs and confirm a clean memory."""
        for did in REQUIRED_DIDS:
            try:
                value = self.api.read_did(did)
                self.api.log(f"DID 0x{did:04X} = {value.decode('ascii', 'replace').strip()}")
            except Exception as exc:  # noqa: BLE001 - recorded as a failure
                self.failures.append(f"DID 0x{did:04X} unreadable: {exc}")

        before = self.api.read_dtcs(0xFF)
        self.api.log(f"{len(before)} DTC(s) present before clearing")
        if not self.api.clear_dtcs():
            self.failures.append("clearing the DTC memory was rejected")
        self.api.wait(300)
        after = self.api.read_dtcs(0xFF)
        if after:
            self.failures.append(f"{len(after)} DTC(s) remain after clearing")

        for problem in self.failures:
            self.api.log(f"FAILURE: {problem}")
        return "PASS" if not self.failures else "FAIL"

    def teardown(self):
        """Reset the ECU so it leaves the line in a defined state."""
        self.api.ecu_reset(0x01)
