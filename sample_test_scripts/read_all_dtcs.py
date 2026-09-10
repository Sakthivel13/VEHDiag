"""Read every stored DTC and summarise them by status."""
from __future__ import annotations


class TestScript:
    """Read confirmed, pending and permanent diagnostic trouble codes."""

    name = "Read all DTCs"

    def __init__(self, api):
        """Store the diagnostic API."""
        self.api = api
        self.dtcs: list[dict] = []

    def setup(self):
        """Enter the extended diagnostic session."""
        self.api.change_session(0x03)

    def execute(self):
        """Read all DTCs; the test passes when the request succeeds."""
        self.dtcs = self.api.read_dtcs(0xFF)
        confirmed = [d for d in self.dtcs if d.get("confirmed")]
        pending = [d for d in self.dtcs if d.get("pending")]
        self.api.log(
            f"{len(self.dtcs)} DTC(s): {len(confirmed)} confirmed, {len(pending)} pending"
        )
        for dtc in self.dtcs:
            self.api.log(f"  {dtc['code']} {dtc['name']} status {dtc['status']}")
        self.api.set_variable("dtcs", self.dtcs)
        return "PASS"

    def teardown(self):
        """Nothing to clean up."""
