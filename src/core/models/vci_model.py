"""Model describing detected VCI hardware and its configuration."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..enums.protocol_enums import ProtocolType
from ..enums.vci_enums import VCICapability, VCIState, VCIType


@dataclass(slots=True)
class VCIDeviceInfo:
    """Static information about a piece of VCI hardware."""

    vci_type: VCIType = VCIType.VIRTUAL
    name: str = "Virtual VCI"
    serial_number: str = ""
    firmware_version: str = ""
    driver_version: str = ""
    channel_count: int = 1
    capabilities: set[VCICapability] = field(default_factory=set)
    extra: dict[str, Any] = field(default_factory=dict)

    def supports(self, capability: VCICapability) -> bool:
        """Return ``True`` when the hardware advertises *capability*."""
        return capability in self.capabilities

    @property
    def label(self) -> str:
        """Return a display label such as ``"PCAN-USB (SN 1234)"``."""
        return f"{self.name} (SN {self.serial_number})" if self.serial_number else self.name


@dataclass(slots=True)
class VCIChannelConfig:
    """Configuration applied when opening a VCI channel.

    Attributes:
        channel: Channel index or interface name (``0``, ``"can0"``, ...).
        protocol: Protocol to run on the channel.
        bitrate: Arbitration bitrate in bit/s.
        data_bitrate: CAN FD data phase bitrate in bit/s.
        sample_point: Optional sample point as a fraction (0..1).
        listen_only: Open the channel without acknowledging frames.
        serial_port: Serial device for K-Line/LIN adapters.
        host: Remote host for Ethernet based interfaces.
        port: Remote TCP/UDP port.
        extra: Vendor specific options passed through to the driver.
    """

    channel: int | str = 0
    protocol: ProtocolType = ProtocolType.CAN
    bitrate: int = 500_000
    data_bitrate: int = 2_000_000
    sample_point: float | None = None
    listen_only: bool = False
    serial_port: str = ""
    host: str = ""
    port: int = 13400
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class VCIStatus:
    """Live status of an opened VCI channel."""

    state: VCIState = VCIState.UNINITIALIZED
    bus_load_percent: float = 0.0
    tx_count: int = 0
    rx_count: int = 0
    error_count: int = 0
    last_error: str = ""

    @property
    def is_connected(self) -> bool:
        """Return ``True`` when the channel is usable."""
        return self.state is VCIState.CONNECTED


__all__ = ["VCIDeviceInfo", "VCIChannelConfig", "VCIStatus"]
