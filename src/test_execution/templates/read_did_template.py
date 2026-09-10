"""Template: read a list of data identifiers and check their content."""
from __future__ import annotations

#: Identifiers read by this template, with the expected minimum length.
DIDS: tuple[tuple[int, int], ...] = (
    (0xF190, 17),   # VIN
    (0xF18C, 1),    # ECU serial number
    (0xF189, 1),    # software version
)


class TestScript:
    """Read several DIDs and verify each one returns enough data."""

    name = "Read data identifiers"

    def __init__(self, api):
        """Store the diagnostic API."""
        self.api = api
        self.values: dict[int, bytes] = {}

    def setup(self):
        """Reading identification data needs the extended session."""
        self.api.change_session(0x03)

    def execute(self):
        """Read every identifier and validate its length."""
        for did, minimum in DIDS:
            data = self.api.read_did(did)
            self.values[did] = data
            self.api.log(f"0x{did:04X} = {data.decode('ascii', 'replace').strip()}")
            self.api.assert_true(
                len(data) >= minimum,
                f"DID 0x{did:04X} returned {len(data)} bytes, expected at least {minimum}",
            )
        self.api.set_variable("did_values", self.values)
        return "PASS"

    def teardown(self):
        """Nothing to clean up."""
