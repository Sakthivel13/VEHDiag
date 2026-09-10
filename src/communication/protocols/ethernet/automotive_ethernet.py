"""Automotive Ethernet helpers shared by DoIP and SOME/IP."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from ....core.enums.protocol_enums import ProtocolType
from ....core.event_bus import EventBus
from ....core.interfaces.i_vci_driver import IVCIDriver
from .doip_protocol import DoIPProtocol
from .ethernet_config import EthernetConfig

_logger = logging.getLogger(__name__)

#: Well known Automotive Ethernet ports.
KNOWN_PORTS: dict[int, str] = {
    13400: "DoIP (ISO 13400)",
    3496: "DoIP over TLS",
    30490: "SOME/IP service discovery",
    30491: "SOME/IP",
}


@dataclass(slots=True)
class EthernetLinkInfo:
    """Description of a discovered Ethernet link."""

    address: str
    port: int
    service: str = ""
    reachable: bool = False

    def __str__(self) -> str:  # noqa: D105 - trivial
        state = "up" if self.reachable else "down"
        return f"{self.address}:{self.port} {self.service} ({state})"


class AutomotiveEthernet(DoIPProtocol):
    """Automotive Ethernet transport.

    In practice the diagnostic use case is always DoIP, so this class is a thin
    specialisation of :class:`DoIPProtocol` that additionally accepts an
    :class:`EthernetConfig` object and exposes link probing helpers.
    """

    def __init__(
        self,
        driver: IVCIDriver | None = None,
        config: EthernetConfig | dict[str, Any] | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        """Accept either a mapping or an :class:`EthernetConfig`."""
        if isinstance(config, EthernetConfig):
            config.validate()
            self.ethernet_config = config
            mapping = config.to_dict()
        else:
            self.ethernet_config = EthernetConfig()
            mapping = dict(config or {})
        super().__init__(driver, mapping, event_bus)  # type: ignore[arg-type]

    @property
    def protocol_type(self) -> ProtocolType:
        """Return :attr:`ProtocolType.ETHERNET`."""
        return ProtocolType.ETHERNET

    @staticmethod
    def probe(host: str, ports: tuple[int, ...] = (13400, 3496, 30490)) -> list[EthernetLinkInfo]:
        """Check which Automotive Ethernet services answer on *host*."""
        from ....utils.network_utils import is_port_open

        return [
            EthernetLinkInfo(
                address=host,
                port=port,
                service=KNOWN_PORTS.get(port, "unknown"),
                reachable=is_port_open(host, port, timeout=0.5),
            )
            for port in ports
        ]


__all__ = ["AutomotiveEthernet", "EthernetLinkInfo", "KNOWN_PORTS"]
