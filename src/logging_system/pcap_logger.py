"""PCAP writer for Ethernet / DoIP traffic."""
from __future__ import annotations

import logging
import struct
from pathlib import Path
from typing import Iterable

from ..core.models.log_entry_model import LogEntry
from ..utils.file_utils import ensure_dir

_logger = logging.getLogger(__name__)

#: Classic PCAP magic number (microsecond resolution, little endian).
PCAP_MAGIC = 0xA1B2C3D4
#: Link type 1 = Ethernet.
LINKTYPE_ETHERNET = 1
#: Maximum captured packet length.
SNAPLEN = 65535


class PcapLogger:
    """Write Ethernet frames (or synthesised ones) into a PCAP file.

    Diagnostic payloads that were not captured at the Ethernet level are
    wrapped into a synthetic Ethernet/IPv4/TCP frame so they can still be
    inspected in Wireshark.

    Example:
        >>> import tempfile, pathlib
        >>> from src.core.models.log_entry_model import LogEntry
        >>> target = pathlib.Path(tempfile.mkdtemp()) / "trace.pcap"
        >>> _ = PcapLogger(target).write_entries([LogEntry(data=b"\\x10\\x03")])
        >>> target.stat().st_size > 24
        True
    """

    def __init__(self, path: str | Path, port: int = 13400) -> None:
        """Store the destination path and the TCP port used in synthetic frames."""
        self.path = Path(path).expanduser()
        self.port = port
        ensure_dir(self.path.parent)

    @staticmethod
    def file_header() -> bytes:
        """Return the 24 byte PCAP global header."""
        return struct.pack(
            "<IHHiIII", PCAP_MAGIC, 2, 4, 0, 0, SNAPLEN, LINKTYPE_ETHERNET
        )

    @staticmethod
    def packet_header(timestamp: float, length: int) -> bytes:
        """Return the 16 byte per-packet header."""
        seconds = int(timestamp)
        micros = int((timestamp - seconds) * 1_000_000)
        return struct.pack("<IIII", seconds, micros, length, length)

    def synthesise_frame(self, payload: bytes, outgoing: bool = True) -> bytes:
        """Wrap *payload* into an Ethernet/IPv4/TCP frame."""
        source_mac = b"\x02\x00\x00\x00\x00\x01"
        target_mac = b"\x02\x00\x00\x00\x00\x02"
        if not outgoing:
            source_mac, target_mac = target_mac, source_mac
        ethernet = target_mac + source_mac + struct.pack(">H", 0x0800)

        tcp_length = 20 + len(payload)
        ip_total = 20 + tcp_length
        source_ip = bytes([192, 168, 0, 1]) if outgoing else bytes([192, 168, 0, 10])
        target_ip = bytes([192, 168, 0, 10]) if outgoing else bytes([192, 168, 0, 1])
        ip = struct.pack(
            ">BBHHHBBH4s4s", 0x45, 0, ip_total, 0, 0x4000, 64, 6, 0, source_ip, target_ip
        )
        source_port = 50000 if outgoing else self.port
        target_port = self.port if outgoing else 50000
        tcp = struct.pack(
            ">HHIIBBHHH", source_port, target_port, 0, 0, 0x50, 0x18, 8192, 0, 0
        )
        return ethernet + ip + tcp + payload

    def write_entries(self, entries: Iterable[LogEntry]) -> Path:
        """Write every entry carrying payload data into the PCAP file."""
        with self.path.open("wb") as handle:
            handle.write(self.file_header())
            for entry in entries:
                if not entry.data:
                    continue
                frame = self.synthesise_frame(entry.data, entry.direction.upper() != "RX")
                handle.write(self.packet_header(entry.timestamp, len(frame)))
                handle.write(frame)
        return self.path


__all__ = ["PcapLogger", "PCAP_MAGIC", "LINKTYPE_ETHERNET"]
