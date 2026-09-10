"""Factory creating the right :class:`IVCIDriver` for a configuration."""
from __future__ import annotations

import logging
from typing import Any, Callable

from ...core.enums.vci_enums import VCIType
from ...core.event_bus import EventBus
from ...core.exceptions import DriverNotFoundError
from ...core.interfaces.i_vci_driver import IVCIDriver
from ...core.models.vci_model import VCIChannelConfig

_logger = logging.getLogger(__name__)

#: Registry of additional drivers contributed by plugins.
_CUSTOM_DRIVERS: dict[str, Callable[..., IVCIDriver]] = {}


def register_driver(name: str, factory: Callable[..., IVCIDriver]) -> None:
    """Register a plugin supplied driver under *name*."""
    _CUSTOM_DRIVERS[name.upper()] = factory
    _logger.info("registered custom VCI driver %s", name)


def unregister_driver(name: str) -> None:
    """Remove a previously registered plugin driver."""
    _CUSTOM_DRIVERS.pop(name.upper(), None)


class VCIFactory:
    """Create VCI drivers, falling back to the virtual driver when needed."""

    @staticmethod
    def create(
        vci_type: VCIType | str,
        config: VCIChannelConfig | None = None,
        event_bus: EventBus | None = None,
        fallback_to_virtual: bool = True,
        **kwargs: Any,
    ) -> IVCIDriver:
        """Instantiate the driver for *vci_type*.

        Args:
            vci_type: Hardware family to instantiate.
            config: Channel configuration passed to the driver.
            event_bus: Bus used by the driver for notifications.
            fallback_to_virtual: Return a virtual driver when the vendor
                library is unavailable instead of raising.
            **kwargs: Forwarded to the driver constructor.

        Returns:
            A ready to configure driver instance.

        Raises:
            DriverNotFoundError: The driver is unavailable and no fallback was
                requested.
        """
        key = vci_type.value if isinstance(vci_type, VCIType) else str(vci_type).upper()
        if key in _CUSTOM_DRIVERS:
            return _CUSTOM_DRIVERS[key](config=config, event_bus=event_bus, **kwargs)
        try:
            return VCIFactory._create_builtin(key, config, event_bus, **kwargs)
        except (ImportError, DriverNotFoundError, OSError) as exc:
            if not fallback_to_virtual:
                raise DriverNotFoundError(
                    f"VCI driver {key} is not available", {"cause": str(exc)}
                ) from exc
            _logger.warning("VCI %s unavailable (%s); falling back to the virtual driver", key, exc)
            from .virtual.virtual_vci_driver import VirtualVCIDriver

            return VirtualVCIDriver(config=config, event_bus=event_bus)

    @staticmethod
    def _create_builtin(
        key: str,
        config: VCIChannelConfig | None,
        event_bus: EventBus | None,
        **kwargs: Any,
    ) -> IVCIDriver:
        """Import and instantiate one of the bundled drivers."""
        if key in ("VIRTUAL", "SIMULATION"):
            from .virtual.virtual_vci_driver import VirtualVCIDriver

            return VirtualVCIDriver(config=config, event_bus=event_bus, **kwargs)
        if key == "PCAN_FD":
            from .pcan.pcan_fd_driver import PCANFDDriver

            return PCANFDDriver(config=config, event_bus=event_bus, **kwargs)
        if key == "PCAN":
            from .pcan.pcan_driver import PCANDriver

            return PCANDriver(config=config, event_bus=event_bus, **kwargs)
        if key == "VECTOR":
            from .vector.vector_driver import VectorDriver

            return VectorDriver(config=config, event_bus=event_bus, **kwargs)
        if key == "KVASER_BLACKBIRD_V2":
            from .kvaser.kvaser_blackbird_v2 import KvaserBlackbirdV2Driver

            return KvaserBlackbirdV2Driver(config=config, event_bus=event_bus, **kwargs)
        if key == "KVASER_LEAF_V3":
            from .kvaser.kvaser_leaf_v3 import KvaserLeafV3Driver

            return KvaserLeafV3Driver(config=config, event_bus=event_bus, **kwargs)
        if key == "KVASER":
            from .kvaser.kvaser_driver import KvaserDriver

            return KvaserDriver(config=config, event_bus=event_bus, **kwargs)
        if key == "INTREPIDCS":
            from .intrepidcs.intrepidcs_driver import IntrepidCSDriver

            return IntrepidCSDriver(config=config, event_bus=event_bus, **kwargs)
        if key == "SOCKETCAN":
            from .pcan.pcan_driver import PythonCanDriver

            return PythonCanDriver(
                interface="socketcan", config=config, event_bus=event_bus, **kwargs
            )
        raise DriverNotFoundError(f"unknown VCI type {key!r}")

    @staticmethod
    def available_types() -> list[str]:
        """Return every VCI identifier the factory can build."""
        return [t.value for t in VCIType] + sorted(_CUSTOM_DRIVERS)


__all__ = ["VCIFactory", "register_driver", "unregister_driver"]
