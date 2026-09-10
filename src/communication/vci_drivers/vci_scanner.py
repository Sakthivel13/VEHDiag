"""Detect VCI hardware attached to the system."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ...core.enums.vci_enums import VCICapability, VCIType
from ...core.event_bus import EventBus, EventType, get_event_bus
from ...utils.platform_utils import list_serial_ports, load_shared_library

_logger = logging.getLogger(__name__)


@dataclass(slots=True)
class DetectedVCI:
    """One interface found on the system."""

    vci_type: VCIType
    name: str
    channel: int | str = 0
    serial_number: str = ""
    capabilities: set[VCICapability] = field(default_factory=set)
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def label(self) -> str:
        """Return the text shown in the device drop-down."""
        suffix = f" - {self.serial_number}" if self.serial_number else ""
        return f"{self.name} (channel {self.channel}){suffix}"


class VCIScanner:
    """Scan USB, network and serial buses for supported interfaces."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        """Create the scanner."""
        self.bus = event_bus or get_event_bus()
        self.last_result: list[DetectedVCI] = []

    def scan(self, include_virtual: bool = True) -> list[DetectedVCI]:
        """Return every interface found, always including the virtual one.

        Example:
            >>> devices = VCIScanner().scan()
            >>> any(d.vci_type.value == "VIRTUAL" for d in devices)
            True
        """
        found: list[DetectedVCI] = []
        found.extend(self._scan_python_can())
        found.extend(self._scan_pcan())
        found.extend(self._scan_kvaser())
        found.extend(self._scan_vector())
        found.extend(self._scan_serial())
        if include_virtual:
            found.append(
                DetectedVCI(
                    vci_type=VCIType.VIRTUAL,
                    name="Virtual VCI (ECU simulator)",
                    channel=0,
                    serial_number="SIM-0001",
                    capabilities={VCICapability.CAN, VCICapability.CAN_FD},
                    details={"always_available": True},
                )
            )
        self.last_result = found
        self.bus.publish(
            EventType.COMM_VCI_DETECTED,
            {"count": len(found), "devices": [d.label for d in found]},
            "VCIScanner",
        )
        return found

    # -- individual scanners ------------------------------------------------
    def _scan_python_can(self) -> list[DetectedVCI]:
        """Use :mod:`can` auto-detection when the library is installed."""
        try:
            from can.interface import detect_available_configs  # type: ignore[import-not-found]
        except Exception:  # noqa: BLE001 - python-can is optional at runtime
            return []
        results: list[DetectedVCI] = []
        try:
            for entry in detect_available_configs():
                interface = str(entry.get("interface", "unknown"))
                channel = entry.get("channel", 0)
                mapping = {
                    "pcan": VCIType.PCAN,
                    "vector": VCIType.VECTOR,
                    "kvaser": VCIType.KVASER_LEAF_V3,
                    "neovi": VCIType.INTREPIDCS,
                    "socketcan": VCIType.SOCKETCAN,
                    "virtual": VCIType.VIRTUAL,
                }
                vci_type = mapping.get(interface, VCIType.SOCKETCAN)
                if vci_type is VCIType.VIRTUAL:
                    continue
                results.append(
                    DetectedVCI(
                        vci_type=vci_type,
                        name=f"{interface} {channel}",
                        channel=channel,
                        capabilities={VCICapability.CAN},
                        details=dict(entry),
                    )
                )
        except Exception:  # noqa: BLE001
            _logger.debug("python-can detection failed", exc_info=True)
        return results

    def _scan_pcan(self) -> list[DetectedVCI]:
        """Probe for the PCANBasic library."""
        if load_shared_library("PCANBasic") is None:
            return []
        return [
            DetectedVCI(
                vci_type=VCIType.PCAN,
                name="PEAK PCAN-USB",
                channel=index,
                capabilities={VCICapability.CAN, VCICapability.CAN_FD},
                details={"handle": f"PCAN_USBBUS{index}"},
            )
            for index in range(1, 3)
        ]

    def _scan_kvaser(self) -> list[DetectedVCI]:
        """Probe for the Kvaser CANlib library."""
        if load_shared_library("canlib") is None and load_shared_library("canlib32") is None:
            return []
        return [
            DetectedVCI(
                vci_type=VCIType.KVASER_LEAF_V3,
                name="Kvaser interface",
                channel=0,
                capabilities={VCICapability.CAN, VCICapability.CAN_FD},
            )
        ]

    def _scan_vector(self) -> list[DetectedVCI]:
        """Probe for the Vector XL driver library."""
        if load_shared_library("vxlapi64") is None and load_shared_library("vxlapi") is None:
            return []
        return [
            DetectedVCI(
                vci_type=VCIType.VECTOR,
                name="Vector XL channel",
                channel=0,
                capabilities={VCICapability.CAN, VCICapability.CAN_FD, VCICapability.LIN},
            )
        ]

    def _scan_serial(self) -> list[DetectedVCI]:
        """Report serial ports usable for K-Line and LIN adapters."""
        return [
            DetectedVCI(
                vci_type=VCIType.SERIAL,
                name=f"Serial adapter {port}",
                channel=port,
                capabilities={VCICapability.KLINE, VCICapability.LIN},
                details={"port": port},
            )
            for port in list_serial_ports()
        ]


__all__ = ["DetectedVCI", "VCIScanner"]
