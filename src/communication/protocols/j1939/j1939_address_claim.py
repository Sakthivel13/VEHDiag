"""J1939 address claiming procedure (SAE J1939-81)."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable

from .j1939_pgn import GLOBAL_ADDRESS, NULL_ADDRESS, J1939Id

_logger = logging.getLogger(__name__)

#: PGN used to announce a claimed address.
ADDRESS_CLAIMED_PGN = 0x00EE00
#: Time a node must wait after claiming before transmitting, in seconds.
CLAIM_SETTLE_TIME_S = 0.25


@dataclass(slots=True)
class J1939Name:
    """The 64-bit NAME of a J1939 controller application.

    Attributes:
        identity_number: 21-bit manufacturer assigned serial number.
        manufacturer_code: 11-bit manufacturer identifier.
        ecu_instance: 3-bit ECU instance.
        function_instance: 5-bit function instance.
        function: 8-bit function code.
        vehicle_system: 7-bit vehicle system.
        vehicle_system_instance: 4-bit vehicle system instance.
        industry_group: 3-bit industry group.
        arbitrary_address_capable: The node may pick another address.
    """

    identity_number: int = 0x000001
    manufacturer_code: int = 0x000
    ecu_instance: int = 0
    function_instance: int = 0
    function: int = 0x81  # off-board diagnostic service tool
    vehicle_system: int = 0
    vehicle_system_instance: int = 0
    industry_group: int = 0
    arbitrary_address_capable: bool = True

    def to_int(self) -> int:
        """Encode the NAME into its 64-bit integer form."""
        return (
            (int(self.arbitrary_address_capable) << 63)
            | ((self.industry_group & 0x07) << 60)
            | ((self.vehicle_system_instance & 0x0F) << 56)
            | ((self.vehicle_system & 0x7F) << 49)
            | ((self.function & 0xFF) << 40)
            | ((self.function_instance & 0x1F) << 35)
            | ((self.ecu_instance & 0x07) << 32)
            | ((self.manufacturer_code & 0x7FF) << 21)
            | (self.identity_number & 0x1FFFFF)
        )

    def to_bytes(self) -> bytes:
        """Encode the NAME as eight little-endian bytes."""
        return self.to_int().to_bytes(8, "little")

    @classmethod
    def from_bytes(cls, raw: bytes) -> "J1939Name":
        """Decode eight little-endian NAME bytes."""
        value = int.from_bytes(raw[:8], "little")
        return cls(
            identity_number=value & 0x1FFFFF,
            manufacturer_code=(value >> 21) & 0x7FF,
            ecu_instance=(value >> 32) & 0x07,
            function_instance=(value >> 35) & 0x1F,
            function=(value >> 40) & 0xFF,
            vehicle_system=(value >> 49) & 0x7F,
            vehicle_system_instance=(value >> 56) & 0x0F,
            industry_group=(value >> 60) & 0x07,
            arbitrary_address_capable=bool(value >> 63),
        )

    def wins_against(self, other: "J1939Name") -> bool:
        """Return ``True`` when this NAME has the higher priority (lower value)."""
        return self.to_int() < other.to_int()


class AddressClaimer:
    """Performs and defends a J1939 address claim.

    Args:
        send_raw: Callable transmitting ``(can_id, payload)``.
        name: NAME of this node.
        preferred_address: Address to claim first.
    """

    def __init__(
        self,
        send_raw: Callable[[int, bytes], None],
        name: J1939Name | None = None,
        preferred_address: int = 0xF9,
    ) -> None:
        """Create the claimer in the unclaimed state."""
        self.send_raw = send_raw
        self.name = name or J1939Name()
        self.preferred_address = preferred_address
        self.address = NULL_ADDRESS
        self.claimed = False

    def claim(self, address: int | None = None) -> None:
        """Broadcast an address claimed message for *address*."""
        target = self.preferred_address if address is None else address
        can_id = J1939Id(
            priority=6,
            pgn=ADDRESS_CLAIMED_PGN,
            source_address=target,
            destination_address=GLOBAL_ADDRESS,
        ).to_can_id()
        self.send_raw(can_id, self.name.to_bytes())
        self.address = target
        self.claimed = True
        time.sleep(CLAIM_SETTLE_TIME_S)
        _logger.info("claimed J1939 address 0x%02X", target)

    def handle_contention(self, contender_name: J1939Name, address: int) -> bool:
        """React to a competing claim for the same address.

        Returns:
            ``True`` when this node keeps the address.
        """
        if address != self.address:
            return True
        if self.name.wins_against(contender_name):
            self.claim(self.address)  # re-assert the claim
            return True
        if self.name.arbitrary_address_capable:
            self.claim(self._next_address())
            return False
        self.address = NULL_ADDRESS
        self.claimed = False
        self.send_raw(
            J1939Id(
                priority=6,
                pgn=ADDRESS_CLAIMED_PGN,
                source_address=NULL_ADDRESS,
                destination_address=GLOBAL_ADDRESS,
            ).to_can_id(),
            self.name.to_bytes(),
        )
        return False

    def _next_address(self) -> int:
        """Return the next address to try in the tool range 128..247."""
        candidate = self.address + 1
        if not 128 <= candidate <= 247:
            candidate = 128
        return candidate


__all__ = ["J1939Name", "AddressClaimer", "ADDRESS_CLAIMED_PGN", "CLAIM_SETTLE_TIME_S"]
