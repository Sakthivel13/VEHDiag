"""VCI hardware selection helpers."""
from __future__ import annotations

from src.communication.vci_drivers.vci_scanner import DetectedVCI, VCIScanner
from src.core.enums.vci_enums import VCICapability, VCIType


def selectable_types() -> list[tuple[str, str]]:
   """Return ``(value, label)`` for every VCI type offered in the UI.

   Example:
       >>> ("VIRTUAL", "Virtual VCI (simulation)") in selectable_types()
       True
   """
   return [(vci.value, vci.display_name) for vci in VCIType]


def describe(device: DetectedVCI) -> dict[str, str]:
   """Return a mapping describing *device* for the device drop-down."""
   return {
       "label": device.label,
       "type": device.vci_type.value,
       "channel": str(device.channel),
       "serial": device.serial_number,
       "capabilities": ", ".join(sorted(c.value for c in device.capabilities)),
   }


def scan(include_virtual: bool = True) -> list[DetectedVCI]:
   """Scan the system and return the detected interfaces."""
   return VCIScanner().scan(include_virtual)


def supports(device: DetectedVCI, capability: VCICapability) -> bool:
   """Return ``True`` when *device* advertises *capability*."""
   return capability in device.capabilities
