"""In-process virtual CAN bus used for development and testing.

Every :class:`VirtualBusNode` attached to a :class:`VirtualBus` receives a copy
of each frame published by the other nodes, so a tester driver and an ECU
simulator can talk to each other without hardware.
"""
from __future__ import annotations

import copy
import queue
import threading
import time
from dataclasses import dataclass, field

from ....core.models.message_model import BusMessage


@dataclass(slots=True)
class VirtualBusStatistics:
    """Counters exposed by the virtual bus for the status bar."""

    frames: int = 0
    dropped: int = 0
    nodes: int = 0


class VirtualBusNode:
    """One endpoint attached to a :class:`VirtualBus`."""

    def __init__(self, name: str, bus: "VirtualBus", queue_size: int = 4096) -> None:
        """Register the node on *bus*."""
        self.name = name
        self.bus = bus
        self.inbox: queue.Queue[BusMessage] = queue.Queue(maxsize=queue_size)

    def send(self, message: BusMessage) -> None:
        """Publish *message* to every other node on the bus."""
        self.bus.publish(message, sender=self)

    def receive(self, timeout: float = 1.0) -> BusMessage | None:
        """Return the next frame addressed to this node, or ``None``."""
        try:
            return self.inbox.get(timeout=max(0.001, timeout))
        except queue.Empty:
            return None

    def deliver(self, message: BusMessage) -> bool:
        """Place *message* in the inbox; return ``False`` when it overflowed."""
        try:
            self.inbox.put_nowait(message)
            return True
        except queue.Full:
            return False

    def flush(self) -> int:
        """Discard every pending frame and return how many were dropped."""
        count = 0
        while True:
            try:
                self.inbox.get_nowait()
                count += 1
            except queue.Empty:
                return count

    def detach(self) -> None:
        """Remove the node from the bus."""
        self.bus.detach(self)


class VirtualBus:
    """A software CAN bus broadcasting frames between attached nodes.

    Example:
        >>> bus = VirtualBus()
        >>> tester, ecu = bus.attach("tester"), bus.attach("ecu")
        >>> tester.send(BusMessage(data=b"\\x02\\x10\\x03", arbitration_id=0x7E0))
        >>> frame = ecu.receive(0.2)
        >>> frame.arbitration_id == 0x7E0
        True
    """

    def __init__(self, name: str = "virtual0", propagation_delay_ms: float = 0.0) -> None:
        """Create an empty bus.

        Args:
            name: Bus name shown in the UI.
            propagation_delay_ms: Artificial delay applied to every frame.
        """
        self.name = name
        self.propagation_delay_ms = propagation_delay_ms
        self.statistics = VirtualBusStatistics()
        self._nodes: list[VirtualBusNode] = []
        self._lock = threading.RLock()

    def attach(self, name: str, queue_size: int = 4096) -> VirtualBusNode:
        """Create and register a new node called *name*."""
        node = VirtualBusNode(name, self, queue_size)
        with self._lock:
            self._nodes.append(node)
            self.statistics.nodes = len(self._nodes)
        return node

    def detach(self, node: VirtualBusNode) -> None:
        """Remove *node* from the bus."""
        with self._lock:
            if node in self._nodes:
                self._nodes.remove(node)
            self.statistics.nodes = len(self._nodes)

    def publish(self, message: BusMessage, sender: VirtualBusNode | None = None) -> None:
        """Broadcast *message* to every node except *sender*."""
        if self.propagation_delay_ms:
            time.sleep(self.propagation_delay_ms / 1000.0)
        with self._lock:
            targets = [n for n in self._nodes if n is not sender]
        self.statistics.frames += 1
        for node in targets:
            copied = copy.copy(message)
            copied.timestamp = time.time()
            copied.channel = self.name
            if not node.deliver(copied):
                self.statistics.dropped += 1

    def clear(self) -> None:
        """Flush every node inbox."""
        with self._lock:
            for node in self._nodes:
                node.flush()

    @property
    def node_names(self) -> list[str]:
        """Return the names of the attached nodes."""
        with self._lock:
            return [n.name for n in self._nodes]

    def __repr__(self) -> str:  # noqa: D105 - trivial
        return f"<VirtualBus {self.name!r} nodes={self.node_names}>"


#: Shared default bus so a driver and a simulator find each other implicitly.
DEFAULT_BUS = VirtualBus("virtual0")


def get_default_bus() -> VirtualBus:
    """Return the process wide default virtual bus."""
    return DEFAULT_BUS


__all__ = [
    "VirtualBus",
    "VirtualBusNode",
    "VirtualBusStatistics",
    "DEFAULT_BUS",
    "get_default_bus",
]
