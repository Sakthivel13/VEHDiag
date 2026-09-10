"""Automotive Ethernet, DoIP and SOME/IP support."""
from __future__ import annotations

from .automotive_ethernet import AutomotiveEthernet, EthernetLinkInfo
from .doip_connection import DoIPConnection, VehicleAnnouncement
from .doip_message import DoIPMessage, PayloadType, build_diagnostic_message
from .doip_protocol import DoIPProtocol
from .doip_routing import RoutingActivationResult, activate_routing
from .ethernet_config import EthernetConfig
from .someip_handler import SomeIPMessage

__all__ = [
    "AutomotiveEthernet",
    "DoIPConnection",
    "DoIPMessage",
    "DoIPProtocol",
    "EthernetConfig",
    "EthernetLinkInfo",
    "PayloadType",
    "RoutingActivationResult",
    "SomeIPMessage",
    "VehicleAnnouncement",
    "activate_routing",
    "build_diagnostic_message",
]
