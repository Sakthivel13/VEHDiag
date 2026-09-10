"""Automotive Ethernet configuration model."""
from __future__ import annotations

from dataclasses import dataclass, field

from ....utils.network_utils import DOIP_PORT, DOIP_TLS_PORT
from ....utils.validation_utils import validate_ip_address, validate_port


@dataclass(slots=True)
class EthernetConfig:
    """Configuration of an Automotive Ethernet / DoIP link.

    Attributes:
        host: IP address of the DoIP entity or gateway.
        port: TCP port used for diagnostic messages.
        discovery_port: UDP port used for vehicle discovery.
        source_address: Logical address of the tester.
        target_address: Logical address of the target ECU.
        activation_type: Routing activation type.
        use_tls: Use TLS for the diagnostic connection.
        interface: Local network interface to bind to.
        vlan_id: Optional VLAN identifier.
        alive_check_interval_ms: Interval of the periodic alive check.
    """

    host: str = "192.168.0.10"
    port: int = DOIP_PORT
    discovery_port: int = DOIP_PORT
    source_address: int = 0x0E00
    target_address: int = 0x1000
    activation_type: int = 0x00
    use_tls: bool = False
    interface: str = ""
    vlan_id: int | None = None
    alive_check_interval_ms: float = 2000.0
    extra: dict[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        """Validate the endpoint parameters.

        Raises:
            ValueError: A field holds an invalid value.
        """
        validate_ip_address(self.host)
        validate_port(self.port)
        validate_port(self.discovery_port)
        for name, value in (("source", self.source_address), ("target", self.target_address)):
            if not 0 <= value <= 0xFFFF:
                raise ValueError(f"{name} address 0x{value:X} is outside 0x0000..0xFFFF")

    @property
    def effective_port(self) -> int:
        """Return the TLS port when TLS is enabled and the default is used."""
        if self.use_tls and self.port == DOIP_PORT:
            return DOIP_TLS_PORT
        return self.port

    def to_dict(self) -> dict[str, object]:
        """Return the mapping consumed by :class:`DoIPProtocol`."""
        return {
            "host": self.host,
            "port": self.effective_port,
            "source_address": self.source_address,
            "target_address": self.target_address,
            "activation_type": self.activation_type,
            "use_tls": self.use_tls,
            "alive_check_interval_ms": self.alive_check_interval_ms,
            **self.extra,
        }


__all__ = ["EthernetConfig"]
