"""Tests for the VCI driver factory.

The factory is the single place that maps a :class:`VCIType` onto a concrete
driver class. A regression here is silent and serious: selecting *PCAN FD* but
receiving a plain :class:`PCANDriver` means the channel is opened in classic
CAN mode and every FD frame is rejected by the hardware.
"""
from __future__ import annotations

import pytest

from src.communication.vci_drivers.vci_factory import (
    VCIFactory,
    register_driver,
    unregister_driver,
)
from src.core.enums.protocol_enums import ProtocolType
from src.core.enums.vci_enums import VCIType
from src.core.exceptions import DriverNotFoundError
from src.core.models.vci_model import VCIChannelConfig


def _config() -> VCIChannelConfig:
    """Return a plain 500 kbit/s channel configuration."""
    return VCIChannelConfig(channel=0, bitrate=500_000)


class TestFactoryMapping:
    """Each VCI type must build its own, most specific driver class."""

    @pytest.mark.parametrize(
        "vci_type,expected",
        [
            (VCIType.PCAN, "PCANDriver"),
            (VCIType.PCAN_FD, "PCANFDDriver"),
            (VCIType.VECTOR, "VectorDriver"),
            (VCIType.KVASER_LEAF_V3, "KvaserLeafV3Driver"),
            (VCIType.KVASER_BLACKBIRD_V2, "KvaserBlackbirdV2Driver"),
            (VCIType.INTREPIDCS, "IntrepidCSDriver"),
            (VCIType.SOCKETCAN, "PythonCanDriver"),
            (VCIType.VIRTUAL, "VirtualVCIDriver"),
        ],
    )
    def test_builds_the_specialised_class(self, vci_type: VCIType, expected: str) -> None:
        """The factory must not collapse a family onto its base driver."""
        driver = VCIFactory.create(vci_type, _config(), fallback_to_virtual=False)
        assert type(driver).__name__ == expected

    def test_pcan_fd_opens_in_fd_mode(self) -> None:
        """Selecting PCAN FD must force the CAN FD protocol."""
        driver = VCIFactory.create(VCIType.PCAN_FD, _config(), fallback_to_virtual=False)
        assert driver.config.protocol is ProtocolType.CAN_FD

    @pytest.mark.parametrize(
        "vci_type",
        [VCIType.KVASER_LEAF_V3, VCIType.KVASER_BLACKBIRD_V2],
    )
    def test_kvaser_variants_keep_their_identity(self, vci_type: VCIType) -> None:
        """A Blackbird must not report itself as a Leaf."""
        driver = VCIFactory.create(vci_type, _config(), fallback_to_virtual=False)
        assert driver.vci_type is vci_type

    def test_backend_selection(self) -> None:
        """Every hardware driver targets the right python-can backend."""
        backends = {
            VCIType.PCAN: "pcan",
            VCIType.VECTOR: "vector",
            VCIType.KVASER_LEAF_V3: "kvaser",
            VCIType.INTREPIDCS: "neovi",
            VCIType.SOCKETCAN: "socketcan",
        }
        for vci_type, backend in backends.items():
            driver = VCIFactory.create(vci_type, _config(), fallback_to_virtual=False)
            assert driver.interface == backend, vci_type


class TestFactoryErrorHandling:
    """Unknown types, fallbacks and plugin registration."""

    def test_unknown_type_raises_without_fallback(self) -> None:
        """A typo must not silently produce a simulator."""
        with pytest.raises(DriverNotFoundError):
            VCIFactory.create("NOT_A_VCI", _config(), fallback_to_virtual=False)

    def test_unknown_type_falls_back_when_asked(self) -> None:
        """With the fallback enabled the virtual driver is returned."""
        driver = VCIFactory.create("NOT_A_VCI", _config(), fallback_to_virtual=True)
        assert type(driver).__name__ == "VirtualVCIDriver"

    def test_available_types_lists_every_family(self) -> None:
        """The UI drop-down is fed from this list."""
        available = VCIFactory.available_types()
        for vci_type in VCIType:
            assert vci_type.value in available

    def test_plugin_driver_takes_precedence(self) -> None:
        """A plugin may register an OEM specific driver."""
        from src.communication.vci_drivers.virtual.virtual_vci_driver import VirtualVCIDriver

        sentinel = []

        def build(**kwargs: object) -> VirtualVCIDriver:
            """Record the call and return a virtual driver."""
            sentinel.append(kwargs)
            return VirtualVCIDriver()

        register_driver("OEM_CUSTOM", build)
        try:
            driver = VCIFactory.create("OEM_CUSTOM", _config(), fallback_to_virtual=False)
            assert sentinel, "the plugin factory was not called"
            assert type(driver).__name__ == "VirtualVCIDriver"
        finally:
            unregister_driver("OEM_CUSTOM")

    def test_hardware_connect_fails_cleanly_without_drivers(self) -> None:
        """No vendor library present must raise, never crash or hang."""
        from src.core.exceptions import ConnectionFailedError

        driver = VCIFactory.create(VCIType.PCAN, _config(), fallback_to_virtual=False)
        with pytest.raises((ConnectionFailedError, DriverNotFoundError)):
            driver.connect()
        assert not driver.is_connected
