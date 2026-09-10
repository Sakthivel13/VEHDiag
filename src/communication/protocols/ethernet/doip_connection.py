"""DoIP TCP/UDP connection handling."""
from __future__ import annotations

import logging
import socket
import ssl
import threading
import time
from dataclasses import dataclass, field

from ....core.exceptions import CommunicationTimeoutError, ConnectionFailedError, SendError
from ....utils.network_utils import DOIP_PORT, DOIP_TLS_PORT, broadcast_address, get_local_addresses
from .doip_message import HEADER_LENGTH, DoIPMessage, PayloadType

_logger = logging.getLogger(__name__)


@dataclass(slots=True)
class VehicleAnnouncement:
    """A vehicle identification / announcement response."""

    vin: str = ""
    logical_address: int = 0
    eid: bytes = b""
    gid: bytes = b""
    further_action: int = 0
    address: str = ""

    @classmethod
    def from_payload(cls, payload: bytes, address: str = "") -> "VehicleAnnouncement":
        """Parse the 32/33 byte vehicle announcement payload."""
        if len(payload) < 32:
            return cls(address=address)
        return cls(
            vin=payload[0:17].decode("ascii", errors="replace").strip("\x00"),
            logical_address=int.from_bytes(payload[17:19], "big"),
            eid=bytes(payload[19:25]),
            gid=bytes(payload[25:31]),
            further_action=payload[31],
            address=address,
        )

    def __str__(self) -> str:  # noqa: D105 - trivial
        return f"{self.vin or 'unknown VIN'} @ {self.address} (0x{self.logical_address:04X})"


class DoIPConnection:
    """A TCP connection to a DoIP entity, plus UDP discovery helpers.

    Args:
        host: IP address of the DoIP entity.
        port: TCP port, normally 13400.
        use_tls: Wrap the socket in TLS (port 3496 by default).
        timeout: Socket timeout in seconds.
    """

    def __init__(
        self,
        host: str,
        port: int = DOIP_PORT,
        use_tls: bool = False,
        timeout: float = 5.0,
    ) -> None:
        """Store the endpoint without connecting."""
        self.host = host
        self.port = DOIP_TLS_PORT if use_tls and port == DOIP_PORT else port
        self.use_tls = use_tls
        self.timeout = timeout
        self._socket: socket.socket | None = None
        self._lock = threading.RLock()
        self._buffer = bytearray()

    # -- lifecycle ----------------------------------------------------------
    @property
    def is_open(self) -> bool:
        """Return ``True`` when the TCP socket is connected."""
        return self._socket is not None

    def open(self) -> None:
        """Establish the TCP (optionally TLS) connection.

        Raises:
            ConnectionFailedError: The entity is unreachable.
        """
        try:
            raw = socket.create_connection((self.host, self.port), timeout=self.timeout)
            raw.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            if self.use_tls:
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                raw = context.wrap_socket(raw, server_hostname=self.host)
            self._socket = raw
        except OSError as exc:
            raise ConnectionFailedError(
                f"could not connect to the DoIP entity {self.host}:{self.port}",
                {"cause": str(exc)},
            ) from exc

    def close(self) -> None:
        """Close the TCP connection."""
        with self._lock:
            if self._socket is not None:
                try:
                    self._socket.close()
                finally:
                    self._socket = None
            self._buffer.clear()

    # -- message exchange ------------------------------------------------------
    def send(self, message: DoIPMessage) -> None:
        """Transmit *message* over the TCP connection.

        Raises:
            SendError: The socket is closed or the write failed.
        """
        with self._lock:
            if self._socket is None:
                raise SendError("the DoIP connection is not open")
            try:
                self._socket.sendall(message.to_bytes())
            except OSError as exc:
                raise SendError("failed to send a DoIP message", {"cause": str(exc)}) from exc

    def receive(self, timeout: float | None = None) -> DoIPMessage | None:
        """Read one complete DoIP message, or ``None`` on timeout."""
        if self._socket is None:
            return None
        deadline = time.perf_counter() + (timeout if timeout is not None else self.timeout)
        while True:
            message = self._take_message()
            if message is not None:
                return message
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                return None
            self._socket.settimeout(remaining)
            try:
                chunk = self._socket.recv(8192)
            except (TimeoutError, socket.timeout):
                return None
            except OSError:
                return None
            if not chunk:
                return None
            self._buffer.extend(chunk)

    def request(self, message: DoIPMessage, timeout: float | None = None) -> DoIPMessage:
        """Send *message* and wait for the next response.

        Raises:
            CommunicationTimeoutError: No response arrived in time.
        """
        self.send(message)
        response = self.receive(timeout)
        if response is None:
            raise CommunicationTimeoutError(
                "no DoIP response received", {"request": message.type_name}
            )
        return response

    def _take_message(self) -> DoIPMessage | None:
        """Pop one complete message from the receive buffer, if available."""
        if len(self._buffer) < HEADER_LENGTH:
            return None
        length = int.from_bytes(self._buffer[4:8], "big")
        total = HEADER_LENGTH + length
        if len(self._buffer) < total:
            return None
        raw = bytes(self._buffer[:total])
        del self._buffer[:total]
        return DoIPMessage.from_bytes(raw)

    # -- discovery ---------------------------------------------------------------
    @staticmethod
    def discover(timeout: float = 2.0, port: int = DOIP_PORT) -> list[VehicleAnnouncement]:
        """Broadcast a vehicle identification request and collect answers.

        Args:
            timeout: How long to listen for announcements, in seconds.
            port: UDP port to broadcast to.

        Returns:
            Every announcement received during the listening window.
        """
        request = DoIPMessage(PayloadType.VEHICLE_IDENTIFICATION_REQUEST).to_bytes()
        found: list[VehicleAnnouncement] = []
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(0.5)
        try:
            targets = {"255.255.255.255"}
            for address in get_local_addresses():
                try:
                    targets.add(broadcast_address(address))
                except ValueError:
                    continue
            for target in targets:
                try:
                    sock.sendto(request, (target, port))
                except OSError:
                    continue
            deadline = time.perf_counter() + timeout
            while time.perf_counter() < deadline:
                try:
                    data, sender = sock.recvfrom(4096)
                except (TimeoutError, socket.timeout):
                    continue
                except OSError:
                    break
                try:
                    message = DoIPMessage.from_bytes(data)
                except Exception:  # noqa: BLE001 - ignore malformed answers
                    continue
                if message.payload_type in (
                    PayloadType.VEHICLE_ANNOUNCEMENT,
                    PayloadType.VEHICLE_IDENTIFICATION_REQUEST,
                ):
                    found.append(VehicleAnnouncement.from_payload(message.payload, sender[0]))
        finally:
            sock.close()
        return found

    def __enter__(self) -> "DoIPConnection":
        """Open the connection for use in a ``with`` block."""
        self.open()
        return self

    def __exit__(self, *exc: object) -> None:
        """Close the connection when leaving a ``with`` block."""
        self.close()


__all__ = ["DoIPConnection", "VehicleAnnouncement"]
