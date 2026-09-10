"""Virtual VCI driver.

The virtual driver implements the full :class:`IVCIDriver` contract on top of
an in-process :class:`VirtualBus`. It optionally starts an :class:`ECUSimulator`
so the application is fully usable without any hardware, and it supports
recording and replaying traffic plus deterministic error injection.
"""
from __future__ import annotations

import logging
import random
import threading
import time
from typing import Any

from ....core.enums.protocol_enums import ProtocolType
from ....core.enums.vci_enums import VCICapability, VCIType
from ....core.event_bus import EventBus
from ....core.exceptions import SendError
from ....core.models.message_model import BusMessage
from ....core.models.vci_model import VCIChannelConfig, VCIDeviceInfo
from ..base_vci_driver import BaseVCIDriver
from .ecu_simulator import ECUSimulator
from .virtual_bus import VirtualBus, VirtualBusNode, get_default_bus

_logger = logging.getLogger(__name__)


class VirtualVCIDriver(BaseVCIDriver):
    """A software-only VCI backed by :class:`VirtualBus`.

    Args:
        config: Channel configuration; only ``protocol`` and ``channel`` matter.
        event_bus: Bus used for connection notifications.
        virtual_bus: Bus to attach to. When omitted a private bus is created
            so that concurrently running drivers never see each other's
            traffic; pass :func:`get_default_bus` explicitly to share one.
        simulator: Pre-built simulator, or ``None`` to create the default one.
        start_simulator: Start the ECU simulator when connecting.

    Example:
        >>> driver = VirtualVCIDriver()
        >>> driver.connect()
        >>> driver.is_connected
        True
        >>> driver.disconnect()
    """

    vci_type = VCIType.VIRTUAL
    capabilities = frozenset(
        {
            VCICapability.CAN,
            VCICapability.CAN_FD,
            VCICapability.LIN,
            VCICapability.KLINE,
            VCICapability.ETHERNET,
            VCICapability.LISTEN_ONLY,
            VCICapability.HARDWARE_TIMESTAMPS,
            VCICapability.BUS_STATISTICS,
        }
    )

    def __init__(
        self,
        config: VCIChannelConfig | None = None,
        event_bus: EventBus | None = None,
        virtual_bus: VirtualBus | None = None,
        simulator: ECUSimulator | None = None,
        start_simulator: bool = True,
        simulator_config: dict[str, Any] | None = None,
    ) -> None:
        """Create the driver without opening the channel."""
        super().__init__(config, event_bus)
        self.virtual_bus = virtual_bus or VirtualBus(f"virtual-{id(self) & 0xFFFF:04X}")
        self.start_simulator = start_simulator
        self.simulator = simulator or ECUSimulator(simulator_config, self.virtual_bus)
        self.node: VirtualBusNode | None = None

        # Behaviour knobs used by tests and by the "error injection" UI.
        self.artificial_delay_ms: float = 0.0
        self.drop_probability: float = 0.0
        self.error_probability: float = 0.0

        self._recording = False
        self._record: list[BusMessage] = []
        self._replay: list[BusMessage] = []
        self._replay_index = 0
        self._lock = threading.RLock()

    # -- template hooks -----------------------------------------------------
    def _do_connect(self) -> None:
        """Attach to the virtual bus and start the simulator."""
        self.node = self.virtual_bus.attach(f"tester-{id(self) & 0xFFFF:04X}")
        if self.start_simulator:
            self.simulator.start()

    def _do_disconnect(self) -> None:
        """Detach from the bus and stop the simulator."""
        if self.start_simulator:
            self.simulator.stop()
        if self.node is not None:
            self.node.detach()
            self.node = None

    def _do_send(self, message: BusMessage) -> None:
        """Publish *message* on the virtual bus, honouring the error knobs.

        Raises:
            SendError: A simulated transmission error occurred.
        """
        if self.node is None:
            raise SendError("virtual driver is not attached to a bus")
        if self.artificial_delay_ms:
            time.sleep(self.artificial_delay_ms / 1000.0)
        if self.error_probability and random.random() < self.error_probability:
            self.status.error_count += 1
            raise SendError("injected virtual transmission error")
        if self.drop_probability and random.random() < self.drop_probability:
            _logger.debug("virtual driver dropped a frame (injection)")
            return
        if self._recording:
            self._record.append(message)
        self.node.send(message)

    def _do_receive(self, timeout: float) -> BusMessage | None:
        """Return the next frame from the bus or from the replay buffer."""
        if self._replay:
            with self._lock:
                if self._replay_index < len(self._replay):
                    message = self._replay[self._replay_index]
                    self._replay_index += 1
                    return message
        if self.node is None:
            return None
        message = self.node.receive(timeout)
        if message is not None and self._recording:
            self._record.append(message)
        return message

    def _build_device_info(self) -> VCIDeviceInfo:
        """Return static information about the simulated hardware."""
        return VCIDeviceInfo(
            vci_type=VCIType.VIRTUAL,
            name="Virtual VCI",
            serial_number="SIM-0001",
            firmware_version="1.0.0",
            driver_version="1.0.0",
            channel_count=1,
            extra={
                "bus": self.virtual_bus.name,
                "simulator": self.start_simulator,
                "nodes": self.virtual_bus.node_names,
            },
        )

    # -- extras ---------------------------------------------------------------
    def flush(self) -> None:
        """Discard any frames buffered for this node."""
        if self.node is not None:
            self.node.flush()

    def start_recording(self) -> None:
        """Begin capturing every frame sent and received."""
        with self._lock:
            self._record.clear()
            self._recording = True

    def stop_recording(self) -> list[BusMessage]:
        """Stop capturing and return the recorded frames."""
        with self._lock:
            self._recording = False
            return list(self._record)

    def load_replay(self, messages: list[BusMessage]) -> None:
        """Replay *messages* instead of reading from the bus."""
        with self._lock:
            self._replay = list(messages)
            self._replay_index = 0

    def clear_replay(self) -> None:
        """Return to live bus operation."""
        with self._lock:
            self._replay.clear()
            self._replay_index = 0

    def inject_errors(self, drop: float = 0.0, error: float = 0.0, delay_ms: float = 0.0) -> None:
        """Configure the failure injection knobs.

        Args:
            drop: Probability (0..1) that a transmitted frame is silently lost.
            error: Probability that :meth:`send` raises :class:`SendError`.
            delay_ms: Artificial delay applied to each transmission.
        """
        self.drop_probability = drop
        self.error_probability = error
        self.artificial_delay_ms = delay_ms

    @property
    def supported_protocols(self) -> tuple[ProtocolType, ...]:
        """Return the protocols the virtual driver can carry."""
        return (
            ProtocolType.CAN,
            ProtocolType.CAN_FD,
            ProtocolType.KLINE,
            ProtocolType.LIN,
            ProtocolType.DOIP,
            ProtocolType.J1939,
        )


__all__ = ["VirtualVCIDriver"]
