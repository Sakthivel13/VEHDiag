"""CAN identifier filtering."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class CANFilter:
    """A single acceptance filter expressed as identifier plus mask.

    A frame is accepted when ``(frame_id & mask) == (can_id & mask)``.
    """

    can_id: int
    mask: int = 0x7FF
    extended: bool = False

    def matches(self, frame_id: int, extended: bool = False) -> bool:
        """Return ``True`` when *frame_id* passes the filter."""
        if extended != self.extended:
            return False
        return (frame_id & self.mask) == (self.can_id & self.mask)

    @classmethod
    def exact(cls, can_id: int, extended: bool = False) -> "CANFilter":
        """Return a filter accepting only *can_id*."""
        mask = 0x1FFFFFFF if extended else 0x7FF
        return cls(can_id=can_id, mask=mask, extended=extended)

    @classmethod
    def range_filter(cls, first: int, last: int, extended: bool = False) -> "CANFilter":
        """Return a filter roughly covering ``first..last``.

        The CAN acceptance hardware can only express prefix ranges, so the mask
        keeps the bits that are identical across the whole range.
        """
        common = ~(first ^ last) & (0x1FFFFFFF if extended else 0x7FF)
        return cls(can_id=first, mask=common, extended=extended)

    def to_python_can(self) -> dict[str, int | bool]:
        """Return the mapping expected by :mod:`can` bus filters."""
        return {"can_id": self.can_id, "can_mask": self.mask, "extended": self.extended}


@dataclass(slots=True)
class CANFilterSet:
    """A collection of filters evaluated with OR semantics."""

    filters: list[CANFilter] = field(default_factory=list)
    enabled: bool = True

    def add(self, can_filter: CANFilter) -> None:
        """Append *can_filter* to the set."""
        self.filters.append(can_filter)

    def clear(self) -> None:
        """Remove every filter (accept all frames)."""
        self.filters.clear()

    def accepts(self, frame_id: int, extended: bool = False) -> bool:
        """Return ``True`` when any filter accepts *frame_id*."""
        if not self.enabled or not self.filters:
            return True
        return any(f.matches(frame_id, extended) for f in self.filters)

    def to_python_can(self) -> list[dict[str, int | bool]]:
        """Return the list form consumed by :mod:`can`."""
        return [f.to_python_can() for f in self.filters]

    @classmethod
    def for_diagnostics(cls, rx_id: int, extended: bool = False) -> "CANFilterSet":
        """Return a set accepting only the diagnostic response identifier."""
        return cls(filters=[CANFilter.exact(rx_id, extended)])

    def __len__(self) -> int:  # noqa: D105 - trivial
        return len(self.filters)


__all__ = ["CANFilter", "CANFilterSet"]
