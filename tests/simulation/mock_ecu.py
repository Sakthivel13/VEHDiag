"""Helpers building preconfigured ECU simulators for the tests."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from src.communication.vci_drivers.virtual.ecu_simulator import ECUSimulator
from src.communication.vci_drivers.virtual.virtual_bus import VirtualBus
from src.utils.file_utils import load_yaml

#: The YAML configuration shipped next to this module.
CONFIG_PATH = Path(__file__).with_name("ecu_simulator_config.yaml")


def load_simulator_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load the simulator configuration from YAML.

    Example:
        >>> config = load_simulator_config()
        >>> config["rx_id"]
        2016
    """
    document = load_yaml(path or CONFIG_PATH, default={}) or {}
    return dict(document.get("ecu_simulator", document))


def make_simulator(bus: VirtualBus | None = None, **overrides: Any) -> ECUSimulator:
    """Return a simulator built from the YAML configuration.

    Args:
        bus: Virtual bus to attach to.
        **overrides: Values replacing entries of the configuration.
    """
    config = load_simulator_config()
    config.update(overrides)
    return ECUSimulator(config, bus)


def make_slow_simulator(bus: VirtualBus | None = None, delay_ms: int = 200) -> ECUSimulator:
    """Return a simulator that answers slowly, to exercise the timeouts."""
    return make_simulator(bus, response_delay_ms=delay_ms)


def make_pending_simulator(bus: VirtualBus | None = None, count: int = 2) -> ECUSimulator:
    """Return a simulator that sends ``0x78`` pending responses."""
    return make_simulator(bus, support_pending_response=True, pending_response_count=count)


def make_flaky_simulator(bus: VirtualBus | None = None, probability: float = 0.3) -> ECUSimulator:
    """Return a simulator that randomly answers with ``busyRepeatRequest``."""
    return make_simulator(
        bus, error_injection={"enabled": True, "probability": probability, "nrc": 0x21}
    )


def make_empty_simulator(bus: VirtualBus | None = None) -> ECUSimulator:
    """Return a simulator without any DTC, used to test the clear flow."""
    return make_simulator(bus, dtcs=[])


__all__ = [
    "CONFIG_PATH",
    "load_simulator_config",
    "make_simulator",
    "make_slow_simulator",
    "make_pending_simulator",
    "make_flaky_simulator",
    "make_empty_simulator",
]
