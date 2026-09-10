"""ECU description model."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..enums.protocol_enums import ProtocolType
from .session_model import SessionState


@dataclass(slots=True)
class ECUAddressing:
    """Addressing parameters used to talk to one ECU."""

    tx_id: int = 0x7E0
    rx_id: int = 0x7E8
    functional_id: int = 0x7DF
    is_extended_id: bool = False
    source_address: int = 0x0E00
    target_address: int = 0x1000
    address_extension: int | None = None

    def __str__(self) -> str:  # noqa: D105 - trivial
        return f"TX=0x{self.tx_id:X} RX=0x{self.rx_id:X}"


@dataclass(slots=True)
class ECUIdentification:
    """Identification data read from the standard 0xF1xx DIDs."""

    vin: str = ""
    ecu_serial_number: str = ""
    hardware_number: str = ""
    software_number: str = ""
    software_version: str = ""
    supplier_id: str = ""
    manufacturing_date: str = ""
    system_name: str = ""

    def as_dict(self) -> dict[str, str]:
        """Return a mapping of populated identification fields."""
        return {
            "VIN": self.vin,
            "ECU serial number": self.ecu_serial_number,
            "Hardware number": self.hardware_number,
            "Software number": self.software_number,
            "Software version": self.software_version,
            "Supplier": self.supplier_id,
            "Manufacturing date": self.manufacturing_date,
            "System name": self.system_name,
        }


@dataclass(slots=True)
class ECU:
    """A diagnostic target reachable over one protocol.

    Attributes:
        name: Display name, e.g. ``"Engine control module"``.
        protocol: Protocol used to reach the ECU.
        addressing: Request/response addressing parameters.
        identification: Data read from identification DIDs.
        state: Live session/security state.
        supported_services: SIDs known to be supported.
        metadata: Free-form OEM specific attributes.
    """

    name: str = "ECU"
    protocol: ProtocolType = ProtocolType.CAN
    addressing: ECUAddressing = field(default_factory=ECUAddressing)
    identification: ECUIdentification = field(default_factory=ECUIdentification)
    state: SessionState = field(default_factory=SessionState)
    supported_services: set[int] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)

    def supports(self, service_id: int) -> bool:
        """Return ``True`` when *service_id* is known to be supported.

        When the supported-service set is empty nothing has been probed yet and
        the method optimistically returns ``True``.
        """
        return not self.supported_services or service_id in self.supported_services

    def __str__(self) -> str:  # noqa: D105 - trivial
        return f"{self.name} [{self.protocol.value}] {self.addressing}"


__all__ = ["ECUAddressing", "ECUIdentification", "ECU"]
