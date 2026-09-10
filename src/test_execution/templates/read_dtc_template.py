"""Template: read the fault memory and fail when a confirmed DTC is present."""
from __future__ import annotations

#: Status mask selecting every stored DTC.
STATUS_MASK = 0xFF

#: DTC codes that are tolerated, for example a known open circuit on a bench.
IGNORED_CODES: tuple[str, ...] = ()


class TestScript:
    """Read every DTC and report the confirmed ones as a failure."""

    name = "Read DTCs"

    def __init__(self, api):
        """Store the diagnostic API."""
        self.api = api

    def setup(self):
        """Enter the extended session."""
        self.api.change_session(0x03)

    def execute(self):
        """Read the fault memory and judge the result."""
        dtcs = self.api.read_dtcs(STATUS_MASK)
        self.api.log(f"{len(dtcs)} DTC(s) stored")
        confirmed = [
            dtc for dtc in dtcs if dtc.get("confirmed") and dtc["code"] not in IGNORED_CODES
        ]
        for dtc in dtcs:
            self.api.log(f"  {dtc['code']} {dtc['name']} status {dtc['status']}")
        self.api.set_variable("dtcs", dtcs)
        if confirmed:
            self.api.log(f"{len(confirmed)} confirmed DTC(s) present")
            return "FAIL"
        return "PASS"

    def teardown(self):
        """Nothing to clean up."""
