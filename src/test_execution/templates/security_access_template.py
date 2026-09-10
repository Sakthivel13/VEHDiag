"""Template: unlock a security level."""
from __future__ import annotations

#: Security level requested by this template (odd sub-function).
LEVEL = 0x01

#: Built-in algorithm, or the name registered by an OEM plugin.
ALGORITHM = "xor_complement"


class TestScript:
    """Perform the seed request and the key submission."""

    name = "Security access"

    def __init__(self, api):
        """Store the diagnostic API."""
        self.api = api

    def setup(self):
        """Security access requires a non-default session."""
        self.api.change_session(0x03)

    def execute(self):
        """Unlock the ECU and report the outcome."""
        unlocked = self.api.security_unlock(LEVEL, ALGORITHM)
        self.api.log(
            f"level 0x{LEVEL:02X} with '{ALGORITHM}': "
            + ("unlocked" if unlocked else "still locked")
        )
        self.api.set_variable("unlocked_level", LEVEL if unlocked else None)
        return "PASS" if unlocked else "FAIL"

    def teardown(self):
        """The unlock stays valid for the remaining steps of the sequence."""
