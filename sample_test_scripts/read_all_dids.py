"""Read every standard identification DID and report the values."""
from __future__ import annotations

#: Data identifiers read by this script.
IDENTIFICATION_DIDS: tuple[tuple[int, str], ...] = (
    (0xF190, "VIN"),
    (0xF187, "Spare part number"),
    (0xF188, "ECU software number"),
    (0xF189, "ECU software version"),
    (0xF18A, "System supplier"),
    (0xF18C, "ECU serial number"),
    (0xF191, "ECU hardware number"),
    (0xF195, "Supplier software version"),
)


class TestScript:
    """Read the identification block of the ECU."""

    name = "Read all identification DIDs"

    def __init__(self, api):
        """Store the diagnostic API."""
        self.api = api
        self.values: dict[str, str] = {}

    def setup(self):
        """Enter the extended diagnostic session."""
        self.api.change_session(0x03)

    def execute(self):
        """Read every DID; the test passes when the VIN could be read."""
        for did, label in IDENTIFICATION_DIDS:
            try:
                data = self.api.read_did(did)
            except Exception as exc:  # noqa: BLE001 - optional DIDs may be absent
                self.api.log(f"{label} (0x{did:04X}): not available ({exc})")
                continue
            text = data.decode("ascii", errors="replace").strip("\x00").strip()
            self.values[label] = text
            self.api.log(f"{label} (0x{did:04X}): {text}")
        self.api.set_variable("identification", self.values)
        return "PASS" if "VIN" in self.values else "FAIL"

    def teardown(self):
        """Return to the default session."""
        self.api.change_session(0x01)
