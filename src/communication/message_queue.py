"""Thread-safe prioritised message queue used between the bus and the client."""
from __future__ import annotations

import heapq
import itertools
import threading
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class Priority(IntEnum):
    """Priority classes; lower values are dequeued first."""

    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass(order=True, slots=True)
class _Item:
    """Internal heap entry keeping insertion order stable within a priority."""

    priority: int
    counter: int
    payload: Any = field(compare=False)


class PriorityMessageQueue(Generic[T]):
    """A bounded priority queue with blocking ``get``/``put`` semantics.

    Example:
        >>> q = PriorityMessageQueue[str]()
        >>> q.put("normal")
        True
        >>> q.put("urgent", Priority.CRITICAL)
        True
        >>> q.get(timeout=0.1)
        'urgent'
    """

    def __init__(self, maxsize: int = 0) -> None:
        """Create the queue.

        Args:
            maxsize: Maximum number of items (``0`` = unbounded).
        """
        self.maxsize = maxsize
        self._heap: list[_Item] = []
        self._counter = itertools.count()
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)
        self._dropped = 0

    def put(self, item: T, priority: Priority = Priority.NORMAL, drop_oldest: bool = True) -> bool:
        """Insert *item*.

        Args:
            item: The payload to enqueue.
            priority: Priority class of the item.
            drop_oldest: When the queue is full, drop the lowest priority item
                instead of rejecting the new one.

        Returns:
            ``True`` when the item was stored.
        """
        with self._not_empty:
            if self.maxsize and len(self._heap) >= self.maxsize:
                if not drop_oldest:
                    self._dropped += 1
                    return False
                self._heap.pop()  # remove the lowest priority / newest entry
                self._dropped += 1
            heapq.heappush(self._heap, _Item(int(priority), next(self._counter), item))
            self._not_empty.notify()
            return True

    def get(self, timeout: float | None = None) -> T | None:
        """Return the highest priority item, or ``None`` on timeout."""
        with self._not_empty:
            if not self._heap and not self._not_empty.wait(timeout):
                return None
            if not self._heap:
                return None
            return self._heap and heapq.heappop(self._heap).payload

    def get_nowait(self) -> T | None:
        """Return an item without blocking, or ``None`` when empty."""
        with self._lock:
            if not self._heap:
                return None
            return heapq.heappop(self._heap).payload

    def clear(self) -> int:
        """Discard every queued item and return how many were removed."""
        with self._lock:
            count = len(self._heap)
            self._heap.clear()
            return count

    def qsize(self) -> int:
        """Return the number of queued items."""
        with self._lock:
            return len(self._heap)

    @property
    def dropped(self) -> int:
        """Return how many items were dropped because the queue was full."""
        return self._dropped

    def __len__(self) -> int:  # noqa: D105 - trivial
        return self.qsize()


__all__ = ["Priority", "PriorityMessageQueue"]
