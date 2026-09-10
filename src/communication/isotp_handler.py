"""ISO 15765-2 (ISO-TP) transport protocol implementation.

The handler converts between arbitrarily long diagnostic payloads and the
4/8/64 byte frames of a CAN or CAN FD bus. It implements single frames, first
frames, consecutive frames and flow control, including block size, separation
time, wait frames and every relevant timeout.

The class is transport agnostic: it is given two callables, one to send a raw
frame and one to receive the next raw frame, so it can be driven by a real VCI
driver, by the virtual bus or by a unit test.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Iterator

from ..core.enums.protocol_enums import FlowStatus, IsoTpAddressingFormat, IsoTpFrameType
from ..core.exceptions import (
    CommunicationTimeoutError,
    FlowControlError,
    FramingError,
    SequenceNumberError,
)
from ..utils.timer_utils import Deadline, busy_wait_us

_logger = logging.getLogger(__name__)

#: Valid CAN FD payload lengths; a frame is padded up to the next value.
CAN_FD_LENGTHS: tuple[int, ...] = (8, 12, 16, 20, 24, 32, 48, 64)

#: Largest payload addressable with the classic 12-bit first-frame length.
MAX_CLASSIC_PAYLOAD = 0xFFF

#: Largest payload addressable with the 32-bit escape length of FF_DL.
MAX_ESCAPE_PAYLOAD = 0xFFFFFFFF


def fd_padded_length(length: int) -> int:
    """Return the smallest legal CAN FD frame size that fits *length* bytes.

    Example:
        >>> fd_padded_length(9)
        12
        >>> fd_padded_length(33)
        48
    """
    for candidate in CAN_FD_LENGTHS:
        if length <= candidate:
            return candidate
    return CAN_FD_LENGTHS[-1]


@dataclass(slots=True)
class IsoTpConfig:
    """Configuration of one ISO-TP connection.

    Attributes:
        addressing_format: Normal, extended or mixed addressing.
        block_size: Number of consecutive frames the peer may send before a new
            flow control frame is required (``0`` = unlimited).
        st_min_ms: Minimum separation time requested from the sender.
        n_bs_timeout_ms: Timeout waiting for a flow control frame.
        n_cr_timeout_ms: Timeout waiting for a consecutive frame.
        n_ar_timeout_ms: Timeout waiting for a frame to be transmitted.
        wait_frame_limit: Maximum number of ``WAIT`` flow control frames.
        tx_padding: Pad transmitted frames to the full frame size.
        padding_byte: Byte used for padding.
        can_fd: Enable 64 byte frames and FD length encoding.
        max_frame_size: Payload capacity of one frame (8 for classic CAN).
        source_address: Address extension byte for extended/mixed addressing.
        target_address: Address extension byte expected on reception.
    """

    addressing_format: IsoTpAddressingFormat = IsoTpAddressingFormat.NORMAL_11BIT
    block_size: int = 8
    st_min_ms: float = 0.0
    n_bs_timeout_ms: float = 1000.0
    n_cr_timeout_ms: float = 1000.0
    n_ar_timeout_ms: float = 1000.0
    wait_frame_limit: int = 10
    tx_padding: bool = True
    padding_byte: int = 0x00
    can_fd: bool = False
    max_frame_size: int = 8
    source_address: int = 0x00
    target_address: int = 0x00

    @property
    def uses_address_extension(self) -> bool:
        """Return ``True`` when a leading address byte is part of every frame."""
        return self.addressing_format in (
            IsoTpAddressingFormat.EXTENDED_11BIT,
            IsoTpAddressingFormat.EXTENDED_29BIT,
            IsoTpAddressingFormat.MIXED_11BIT,
            IsoTpAddressingFormat.MIXED_29BIT,
        )

    @property
    def frame_capacity(self) -> int:
        """Return the usable bytes per frame after the address extension."""
        capacity = 64 if self.can_fd else 8
        capacity = min(capacity, self.max_frame_size if self.max_frame_size else capacity)
        return capacity - (1 if self.uses_address_extension else 0)


def encode_st_min(st_min_ms: float) -> int:
    """Encode a separation time in milliseconds into the STmin byte.

    Values from 0 to 127 ms map directly; 100..900 microseconds map to
    ``0xF1``..``0xF9``.

    Example:
        >>> encode_st_min(10)
        10
        >>> hex(encode_st_min(0.5))
        '0xf5'
    """
    if st_min_ms <= 0:
        return 0x00
    if st_min_ms >= 1:
        return min(127, int(round(st_min_ms)))
    tenths = int(round(st_min_ms * 10))
    return 0xF0 + max(1, min(9, tenths))


def decode_st_min(value: int) -> float:
    """Decode an STmin byte into milliseconds.

    Example:
        >>> decode_st_min(0x0A)
        10.0
        >>> decode_st_min(0xF5)
        0.5
    """
    if 0x00 <= value <= 0x7F:
        return float(value)
    if 0xF1 <= value <= 0xF9:
        return (value - 0xF0) / 10.0
    return 0.0  # reserved values are treated as 127 ms by ISO; 0 keeps us fast


@dataclass(slots=True)
class IsoTpStatistics:
    """Counters exposed to the UI for diagnostics of the transport layer."""

    frames_sent: int = 0
    frames_received: int = 0
    messages_sent: int = 0
    messages_received: int = 0
    flow_control_sent: int = 0
    flow_control_received: int = 0
    wait_frames: int = 0
    timeouts: int = 0
    errors: int = 0


class IsoTpHandler:
    """Segmentation and reassembly engine for ISO 15765-2.

    Args:
        send_frame: Callable transmitting one raw frame payload.
        receive_frame: Callable returning the next raw frame payload or
            ``None`` when the given timeout elapses.
        config: Connection parameters.

    Example:
        >>> sent = []
        >>> handler = IsoTpHandler(sent.append, lambda t: None, IsoTpConfig())
        >>> handler.send(bytes.fromhex("22F190"))
        >>> sent[0].hex()
        '0322f1900000000000'
    """

    def __init__(
        self,
        send_frame: Callable[[bytes], None],
        receive_frame: Callable[[float], bytes | None],
        config: IsoTpConfig | None = None,
    ) -> None:
        """Store the transport callbacks and the configuration."""
        self._send_frame = send_frame
        self._receive_frame = receive_frame
        self.config = config or IsoTpConfig()
        self.statistics = IsoTpStatistics()
        self._lock = threading.RLock()
        self._rx_buffer = bytearray()
        self._rx_expected = 0
        self._rx_sequence = 0

    # -- public API ---------------------------------------------------------
    def send(self, payload: bytes) -> None:
        """Transmit *payload*, segmenting it when it exceeds one frame.

        Args:
            payload: Complete diagnostic payload (starting with the SID).

        Raises:
            ValueError: The payload is empty or exceeds the protocol limit.
            FlowControlError: The receiver refused or aborted the transfer.
            CommunicationTimeoutError: No flow control frame arrived in time.
        """
        if not payload:
            raise ValueError("cannot send an empty ISO-TP payload")
        if len(payload) > MAX_ESCAPE_PAYLOAD:
            raise ValueError(f"payload of {len(payload)} bytes exceeds the ISO-TP limit")
        with self._lock:
            if self._fits_single_frame(payload):
                self._send_single_frame(payload)
            else:
                self._send_multi_frame(payload)
            self.statistics.messages_sent += 1

    def receive(self, timeout: float = 1.0) -> bytes | None:
        """Receive and reassemble one complete payload.

        Args:
            timeout: Overall timeout in seconds for the first frame.

        Returns:
            The reassembled payload, or ``None`` when nothing arrived.

        Raises:
            FramingError: A frame violated the ISO-TP framing rules.
            SequenceNumberError: A consecutive frame arrived out of order.
        """
        deadline = Deadline(timeout)
        while not deadline.expired:
            frame = self._receive_frame(deadline.remaining)
            if frame is None:
                break
            self.statistics.frames_received += 1
            payload = self._handle_frame(frame)
            if payload is not None:
                self.statistics.messages_received += 1
                return payload
        return None

    def reset(self) -> None:
        """Discard any partially reassembled message."""
        with self._lock:
            self._rx_buffer.clear()
            self._rx_expected = 0
            self._rx_sequence = 0

    # -- transmission internals ------------------------------------------------
    def _fits_single_frame(self, payload: bytes) -> bool:
        """Return ``True`` when *payload* fits into a single frame."""
        capacity = self.config.frame_capacity
        if self.config.can_fd and len(payload) > 7:
            # FD single frames use a two byte PCI (0x00 + length).
            return len(payload) <= capacity - 2
        return len(payload) <= capacity - 1

    def _send_single_frame(self, payload: bytes) -> None:
        """Transmit *payload* as a single frame."""
        if self.config.can_fd and len(payload) > 7:
            pci = bytes([0x00, len(payload)])
        else:
            pci = bytes([(IsoTpFrameType.SINGLE_FRAME << 4) | len(payload)])
        self._transmit(pci + payload)

    def _send_multi_frame(self, payload: bytes) -> None:
        """Transmit *payload* as first frame plus consecutive frames."""
        capacity = self.config.frame_capacity
        total = len(payload)
        if total <= MAX_CLASSIC_PAYLOAD:
            header = bytes([(IsoTpFrameType.FIRST_FRAME << 4) | (total >> 8), total & 0xFF])
        else:
            header = bytes([IsoTpFrameType.FIRST_FRAME << 4, 0x00]) + total.to_bytes(4, "big")
        first_chunk = payload[: capacity - len(header)]
        self._transmit(header + first_chunk, pad_to_full=True)

        index = len(first_chunk)
        sequence = 1
        block_remaining = 0
        st_min_ms = self.config.st_min_ms

        flow = self._await_flow_control()
        block_remaining, st_min_ms = flow

        while index < total:
            if block_remaining == 0 and self._current_block_size:
                flow = self._await_flow_control()
                block_remaining, st_min_ms = flow
            chunk = payload[index : index + capacity - 1]
            pci = bytes([(IsoTpFrameType.CONSECUTIVE_FRAME << 4) | (sequence & 0x0F)])
            self._transmit(pci + chunk, pad_to_full=True)
            index += len(chunk)
            sequence = (sequence + 1) & 0x0F
            if block_remaining:
                block_remaining -= 1
            self._wait_st_min(st_min_ms)

    @property
    def _current_block_size(self) -> int:
        """Return the block size negotiated for the running transmission."""
        return self._negotiated_block_size

    _negotiated_block_size: int = 0

    def _await_flow_control(self) -> tuple[int, float]:
        """Wait for a flow control frame and return ``(block_size, st_min)``.

        Raises:
            CommunicationTimeoutError: No flow control frame arrived within N_Bs.
            FlowControlError: The receiver reported an overflow or sent too many
                wait frames.
        """
        waits = 0
        while True:
            deadline = Deadline(self.config.n_bs_timeout_ms / 1000.0)
            frame = self._receive_frame(deadline.remaining)
            if frame is None:
                self.statistics.timeouts += 1
                raise CommunicationTimeoutError(
                    "no ISO-TP flow control frame received (N_Bs timeout)",
                    {"timeout_ms": self.config.n_bs_timeout_ms},
                )
            body = self._strip_address_extension(frame)
            if not body:
                continue
            if (body[0] >> 4) != IsoTpFrameType.FLOW_CONTROL:
                # Unrelated frame on the same identifier: ignore it.
                continue
            self.statistics.flow_control_received += 1
            status = body[0] & 0x0F
            if status == FlowStatus.OVERFLOW:
                self.statistics.errors += 1
                raise FlowControlError("the receiver reported an ISO-TP buffer overflow")
            if status == FlowStatus.WAIT:
                waits += 1
                self.statistics.wait_frames += 1
                if waits > self.config.wait_frame_limit:
                    raise FlowControlError(
                        "too many ISO-TP wait frames received",
                        {"limit": self.config.wait_frame_limit},
                    )
                continue
            if status != FlowStatus.CONTINUE_TO_SEND:
                raise FlowControlError(f"invalid ISO-TP flow status 0x{status:X}")
            block_size = body[1] if len(body) > 1 else 0
            st_min = decode_st_min(body[2]) if len(body) > 2 else 0.0
            self._negotiated_block_size = block_size
            return block_size, st_min

    def _wait_st_min(self, st_min_ms: float) -> None:
        """Honour the separation time requested by the receiver."""
        if st_min_ms <= 0:
            return
        if st_min_ms < 1.0:
            busy_wait_us(st_min_ms * 1000.0)
        else:
            time.sleep(st_min_ms / 1000.0)

    def _transmit(self, body: bytes, pad_to_full: bool = True) -> None:
        """Add addressing/padding to *body* and hand it to the transport."""
        if self.config.uses_address_extension:
            body = bytes([self.config.target_address & 0xFF]) + body
        if self.config.tx_padding and pad_to_full:
            target = fd_padded_length(len(body)) if self.config.can_fd else 8
            if len(body) < target:
                body = body + bytes([self.config.padding_byte & 0xFF]) * (target - len(body))
        elif self.config.tx_padding and not self.config.can_fd and len(body) < 8:
            body = body + bytes([self.config.padding_byte & 0xFF]) * (8 - len(body))
        self._send_frame(body)
        self.statistics.frames_sent += 1

    # -- reception internals ------------------------------------------------------
    def _strip_address_extension(self, frame: bytes) -> bytes:
        """Remove the leading address byte for extended/mixed addressing."""
        if not self.config.uses_address_extension:
            return frame
        if not frame:
            return frame
        return frame[1:]

    def _handle_frame(self, frame: bytes) -> bytes | None:
        """Process one received frame; return a payload when it completes one."""
        body = self._strip_address_extension(frame)
        if not body:
            return None
        frame_type = body[0] >> 4
        if frame_type == IsoTpFrameType.SINGLE_FRAME:
            return self._handle_single_frame(body)
        if frame_type == IsoTpFrameType.FIRST_FRAME:
            self._handle_first_frame(body)
            return self._receive_remaining()
        if frame_type == IsoTpFrameType.CONSECUTIVE_FRAME:
            # A stray consecutive frame without a first frame is ignored.
            return None
        if frame_type == IsoTpFrameType.FLOW_CONTROL:
            return None
        raise FramingError(f"unknown ISO-TP frame type 0x{frame_type:X}")

    def _handle_single_frame(self, body: bytes) -> bytes:
        """Extract the payload of a single frame."""
        length = body[0] & 0x0F
        offset = 1
        if length == 0 and self.config.can_fd:
            if len(body) < 2:
                raise FramingError("truncated CAN FD single frame")
            length = body[1]
            offset = 2
        if length == 0:
            raise FramingError("ISO-TP single frame with zero length")
        payload = body[offset : offset + length]
        if len(payload) < length:
            raise FramingError(
                f"single frame declares {length} bytes but carries {len(payload)}"
            )
        return bytes(payload)

    def _handle_first_frame(self, body: bytes) -> None:
        """Start the reassembly of a segmented message and send flow control."""
        if len(body) < 2:
            raise FramingError("truncated ISO-TP first frame")
        length = ((body[0] & 0x0F) << 8) | body[1]
        offset = 2
        if length == 0:
            if len(body) < 6:
                raise FramingError("truncated ISO-TP escape sequence first frame")
            length = int.from_bytes(body[2:6], "big")
            offset = 6
        self._rx_buffer = bytearray(body[offset:])
        self._rx_expected = length
        self._rx_sequence = 1
        self._send_flow_control(FlowStatus.CONTINUE_TO_SEND)

    def _receive_remaining(self) -> bytes | None:
        """Collect consecutive frames until the message is complete."""
        received_in_block = 0
        while len(self._rx_buffer) < self._rx_expected:
            frame = self._receive_frame(self.config.n_cr_timeout_ms / 1000.0)
            if frame is None:
                self.statistics.timeouts += 1
                raise CommunicationTimeoutError(
                    "no ISO-TP consecutive frame received (N_Cr timeout)",
                    {"received": len(self._rx_buffer), "expected": self._rx_expected},
                )
            self.statistics.frames_received += 1
            body = self._strip_address_extension(frame)
            if not body or (body[0] >> 4) != IsoTpFrameType.CONSECUTIVE_FRAME:
                continue
            sequence = body[0] & 0x0F
            if sequence != self._rx_sequence:
                self.statistics.errors += 1
                raise SequenceNumberError(
                    "ISO-TP consecutive frame out of order",
                    {"expected": self._rx_sequence, "received": sequence},
                )
            self._rx_buffer.extend(body[1:])
            self._rx_sequence = (self._rx_sequence + 1) & 0x0F
            received_in_block += 1
            if self.config.block_size and received_in_block >= self.config.block_size:
                if len(self._rx_buffer) < self._rx_expected:
                    self._send_flow_control(FlowStatus.CONTINUE_TO_SEND)
                received_in_block = 0
        payload = bytes(self._rx_buffer[: self._rx_expected])
        self.reset()
        return payload

    def _send_flow_control(self, status: FlowStatus) -> None:
        """Transmit a flow control frame with the configured BS and STmin."""
        body = bytes(
            [
                (IsoTpFrameType.FLOW_CONTROL << 4) | int(status),
                self.config.block_size & 0xFF,
                encode_st_min(self.config.st_min_ms),
            ]
        )
        self._transmit(body, pad_to_full=True)
        self.statistics.flow_control_sent += 1

    # -- helpers ---------------------------------------------------------------------
    def iter_frames(self, payload: bytes) -> Iterator[bytes]:
        """Yield the frames *payload* would be split into (without sending).

        This is used by the trace viewer to preview segmentation and by unit
        tests; flow control is assumed to always permit transmission.
        """
        capacity = self.config.frame_capacity
        if self._fits_single_frame(payload):
            if self.config.can_fd and len(payload) > 7:
                yield bytes([0x00, len(payload)]) + payload
            else:
                yield bytes([len(payload)]) + payload
            return
        total = len(payload)
        header = bytes([(IsoTpFrameType.FIRST_FRAME << 4) | (total >> 8), total & 0xFF])
        first = payload[: capacity - 2]
        yield header + first
        index, sequence = len(first), 1
        while index < total:
            chunk = payload[index : index + capacity - 1]
            yield bytes([(IsoTpFrameType.CONSECUTIVE_FRAME << 4) | (sequence & 0x0F)]) + chunk
            index += len(chunk)
            sequence = (sequence + 1) & 0x0F


__all__ = [
    "CAN_FD_LENGTHS",
    "MAX_CLASSIC_PAYLOAD",
    "MAX_ESCAPE_PAYLOAD",
    "IsoTpConfig",
    "IsoTpStatistics",
    "IsoTpHandler",
    "encode_st_min",
    "decode_st_min",
    "fd_padded_length",
]
