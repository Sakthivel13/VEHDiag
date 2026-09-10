"""Block sequence counter management for TransferData."""
from __future__ import annotations

from dataclasses import dataclass

from ....core.exceptions import TransferError


@dataclass(slots=True)
class BlockSequenceCounter:
    """The 8-bit wrapping counter used by SID 0x36.

    The counter starts at 1 for the first block and wraps from 255 back to 0.

    Example:
        >>> bsc = BlockSequenceCounter()
        >>> bsc.next()
        1
        >>> bsc.next()
        2
        >>> bsc.reset(); bsc.value
        0
    """

    value: int = 0

    def next(self) -> int:
        """Advance the counter and return the new value."""
        self.value = (self.value + 1) & 0xFF
        return self.value

    def peek(self) -> int:
        """Return the value the next call to :meth:`next` would produce."""
        return (self.value + 1) & 0xFF

    def reset(self) -> None:
        """Reset the counter so the next block is number 1."""
        self.value = 0

    def verify(self, echoed: int) -> None:
        """Check the counter echoed by the ECU.

        Raises:
            TransferError: The ECU echoed a different counter value.
        """
        if echoed != self.value:
            raise TransferError(
                "the ECU echoed a wrong block sequence counter",
                {"expected": self.value, "received": echoed},
            )

    def rollback(self) -> int:
        """Step the counter back, used when a block must be retransmitted."""
        self.value = (self.value - 1) & 0xFF
        return self.value


__all__ = ["BlockSequenceCounter"]
