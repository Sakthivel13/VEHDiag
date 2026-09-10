"""DTC status mask helpers."""
from __future__ import annotations

from dataclasses import dataclass

from ....core.models.dtc_model import DTC_STATUS_BITS

#: Mask accepting every DTC regardless of its status.
MASK_ALL = 0xFF
#: Mask matching only confirmed DTCs.
MASK_CONFIRMED = 0x08
#: Mask matching pending DTCs.
MASK_PENDING = 0x04
#: Mask matching DTCs that are currently failing.
MASK_TEST_FAILED = 0x01
#: Mask matching DTCs requesting the warning indicator.
MASK_WARNING = 0x80

#: Short labels used for the mask checkboxes in the UI.
BIT_ABBREVIATIONS: dict[int, str] = {
    0: "TF",
    1: "TFTOC",
    2: "PD",
    3: "CD",
    4: "TNCSLC",
    5: "TFSLC",
    6: "TNCTOC",
    7: "WIR",
}


@dataclass(slots=True)
class StatusMask:
    """A DTC status mask with per-bit accessors.

    Example:
        >>> mask = StatusMask.from_bits(confirmed=True, pending=True)
        >>> hex(mask.value)
        '0xc'
        >>> mask.active_names()
        ['pendingDTC', 'confirmedDTC']
    """

    value: int = MASK_ALL

    def bit(self, index: int) -> bool:
        """Return the state of bit *index*."""
        return bool(self.value & (1 << index))

    def set_bit(self, index: int, state: bool) -> None:
        """Set or clear bit *index*."""
        if state:
            self.value |= 1 << index
        else:
            self.value &= ~(1 << index) & 0xFF

    def active_names(self) -> list[str]:
        """Return the ISO names of the set bits."""
        return [name for index, name in DTC_STATUS_BITS.items() if self.bit(index)]

    def abbreviations(self) -> list[str]:
        """Return the short labels of the set bits."""
        return [text for index, text in BIT_ABBREVIATIONS.items() if self.bit(index)]

    def matches(self, status: int) -> bool:
        """Return ``True`` when *status* has at least one bit in common."""
        return bool(status & self.value)

    @classmethod
    def from_bits(
        cls,
        test_failed: bool = False,
        test_failed_this_cycle: bool = False,
        pending: bool = False,
        confirmed: bool = False,
        test_not_completed_since_clear: bool = False,
        test_failed_since_clear: bool = False,
        test_not_completed_this_cycle: bool = False,
        warning_indicator: bool = False,
    ) -> "StatusMask":
        """Build a mask from individual boolean flags."""
        flags = (
            test_failed,
            test_failed_this_cycle,
            pending,
            confirmed,
            test_not_completed_since_clear,
            test_failed_since_clear,
            test_not_completed_this_cycle,
            warning_indicator,
        )
        value = 0
        for index, flag in enumerate(flags):
            if flag:
                value |= 1 << index
        return cls(value)

    def __int__(self) -> int:  # noqa: D105 - trivial
        return self.value

    def __str__(self) -> str:  # noqa: D105 - trivial
        return f"0x{self.value:02X} [" + ", ".join(self.abbreviations()) + "]"


def describe_status(status: int) -> str:
    """Return a readable description of a DTC status byte.

    Example:
        >>> describe_status(0x08)
        '0x08 [confirmedDTC]'
    """
    names = [name for index, name in DTC_STATUS_BITS.items() if status & (1 << index)]
    return f"0x{status:02X} [" + ", ".join(names) + "]"


__all__ = [
    "StatusMask",
    "describe_status",
    "MASK_ALL",
    "MASK_CONFIRMED",
    "MASK_PENDING",
    "MASK_TEST_FAILED",
    "MASK_WARNING",
    "BIT_ABBREVIATIONS",
]
