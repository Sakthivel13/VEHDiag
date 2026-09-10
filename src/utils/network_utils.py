"""Network helpers, primarily for DoIP discovery."""
from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass

#: Default UDP/TCP port defined by ISO 13400 for DoIP.
DOIP_PORT = 13400
#: Port used for DoIP over TLS.
DOIP_TLS_PORT = 3496


@dataclass(slots=True)
class NetworkInterface:
    """A local network interface usable for DoIP communication."""

    name: str
    address: str
    broadcast: str = ""

    def __str__(self) -> str:  # noqa: D105 - trivial
        return f"{self.name} ({self.address})"


def get_local_addresses() -> list[str]:
    """Return the IPv4 addresses assigned to this host."""
    addresses: set[str] = set()
    hostname = socket.gethostname()
    try:
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            addresses.add(info[4][0])
    except socket.gaierror:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))
            addresses.add(probe.getsockname()[0])
    except OSError:
        pass
    addresses.discard("127.0.0.1")
    return sorted(addresses)


def broadcast_address(address: str, prefix: int = 24) -> str:
    """Return the broadcast address of the network containing *address*."""
    network = ipaddress.ip_network(f"{address}/{prefix}", strict=False)
    return str(network.broadcast_address)


def is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    """Return ``True`` when a TCP connection to ``host:port`` succeeds."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def resolve_host(host: str) -> str:
    """Resolve *host* to an IPv4 address, returning *host* on failure."""
    try:
        return socket.gethostbyname(host)
    except socket.gaierror:
        return host


def create_udp_socket(bind_port: int = 0, broadcast: bool = True, timeout: float = 2.0) -> socket.socket:
    """Create a configured UDP socket for DoIP vehicle discovery."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if broadcast:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(timeout)
    if bind_port:
        sock.bind(("", bind_port))
    return sock


def create_tcp_socket(host: str, port: int = DOIP_PORT, timeout: float = 5.0) -> socket.socket:
    """Create a connected TCP socket with TCP_NODELAY enabled."""
    sock = socket.create_connection((host, port), timeout=timeout)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    return sock


__all__ = [
    "DOIP_PORT",
    "DOIP_TLS_PORT",
    "NetworkInterface",
    "get_local_addresses",
    "broadcast_address",
    "is_port_open",
    "resolve_host",
    "create_udp_socket",
    "create_tcp_socket",
]
