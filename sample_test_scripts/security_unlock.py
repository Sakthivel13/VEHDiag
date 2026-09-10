"""Unlock security level 1 using the built-in demo algorithm."""
from __future__ import annotations

#: Security level requested by this script.
SECURITY_LEVEL = 0x01
#: Built-in algorithm matching the bundled ECU simulator.
ALGORITHM = "xor_complement"


class TestScript:
    """Perform a full seed request and key submission."""

    name = "Security unlock level 1"

    def __init__(self, api):
        """Store the diagnostic API."""
        self.api = api

    def setup(self):
        """Security access requires a non-default session."""
        self.api.change_session(0x03)

    def execute(self):
        """Unlock the ECU and report the outcome."""
        unlocked = self.api.security_unlock(SECURITY_LEVEL, ALGORITHM)
        self.api.log(
            f"security level 0x{SECURITY_LEVEL:02X}: {'unlocked' if unlocked else 'still locked'}"
        )
        return "PASS" if unlocked else "FAIL"

    def teardown(self):
        """Nothing to clean up; the session keeps the unlock state."""
