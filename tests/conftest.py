"""Shared pytest fixtures."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.communication.connection_manager import ConnectionManager, ConnectionProfile  # noqa: E402
from src.communication.vci_drivers.virtual.ecu_simulator import ECUSimulator  # noqa: E402
from src.communication.vci_drivers.virtual.virtual_bus import VirtualBus  # noqa: E402
from src.communication.vci_drivers.virtual.virtual_vci_driver import VirtualVCIDriver  # noqa: E402
from src.core.configuration_manager import ConfigurationManager  # noqa: E402
from src.core.event_bus import EventBus  # noqa: E402
from src.diagnostics.uds_client import UDSClient  # noqa: E402


@pytest.fixture()
def event_bus() -> EventBus:
    """Return a fresh event bus isolated from the global one."""
    return EventBus("test")


@pytest.fixture()
def config(tmp_path: Path) -> ConfigurationManager:
    """Return a configuration manager writing into a temporary directory."""
    return ConfigurationManager(user_config=tmp_path / "user_config.yaml")


@pytest.fixture()
def virtual_bus() -> VirtualBus:
    """Return an isolated virtual CAN bus."""
    return VirtualBus("test0")


@pytest.fixture()
def simulator(virtual_bus: VirtualBus) -> ECUSimulator:
    """Return an ECU simulator attached to the isolated bus."""
    return ECUSimulator(bus=virtual_bus)


@pytest.fixture()
def driver(virtual_bus: VirtualBus, simulator: ECUSimulator, event_bus: EventBus):
    """Return a connected virtual VCI driver."""
    instance = VirtualVCIDriver(
        event_bus=event_bus, virtual_bus=virtual_bus, simulator=simulator
    )
    instance.connect()
    yield instance
    instance.disconnect()


@pytest.fixture()
def transport(driver, event_bus: EventBus):
    """Return a connected transport layer over the virtual driver."""
    from src.communication.protocols.can.can_protocol import CANProtocol
    from src.communication.transport_layer import TransportLayer

    layer = TransportLayer(CANProtocol(driver, event_bus=event_bus), event_bus=event_bus)
    layer.connect()
    yield layer
    layer.disconnect()


@pytest.fixture()
def client(transport, event_bus: EventBus) -> UDSClient:
    """Return a UDS client talking to the simulated ECU."""
    return UDSClient(transport, event_bus=event_bus)


@pytest.fixture()
def connection(config: ConfigurationManager, event_bus: EventBus):
    """Return a connected :class:`ConnectionManager`."""
    manager = ConnectionManager(config, event_bus)
    manager.connect(ConnectionProfile())
    yield manager
    manager.disconnect()
