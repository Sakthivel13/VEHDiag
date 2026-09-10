"""Unit tests for the ISO 15765-2 handler."""
from __future__ import annotations

import queue
import threading

import pytest

from src.communication.isotp_handler import (
    IsoTpConfig,
    IsoTpHandler,
    decode_st_min,
    encode_st_min,
    fd_padded_length,
)
from src.core.exceptions import CommunicationTimeoutError, FlowControlError, SequenceNumberError


def make_pair(config_a: IsoTpConfig | None = None, config_b: IsoTpConfig | None = None):
    """Return two handlers connected through in-memory queues."""
    queue_a: queue.Queue[bytes] = queue.Queue()
    queue_b: queue.Queue[bytes] = queue.Queue()

    def receiver(source: queue.Queue[bytes]):
        def receive(timeout: float) -> bytes | None:
            try:
                return source.get(timeout=max(0.001, timeout))
            except queue.Empty:
                return None

        return receive

    first = IsoTpHandler(queue_b.put, receiver(queue_a), config_a or IsoTpConfig())
    second = IsoTpHandler(queue_a.put, receiver(queue_b), config_b or IsoTpConfig())
    return first, second


def exchange(sender: IsoTpHandler, receiver: IsoTpHandler, payload: bytes, timeout: float = 5.0):
    """Send *payload* from *sender* and return what *receiver* reassembled."""
    result: dict[str, bytes | None] = {}

    def reader() -> None:
        result["payload"] = receiver.receive(timeout)

    thread = threading.Thread(target=reader)
    thread.start()
    sender.send(payload)
    thread.join(timeout)
    return result.get("payload")


class TestSingleFrame:
    """Single frame transmission and reception."""

    def test_short_payload_is_single_frame(self) -> None:
        """A payload of up to seven bytes fits into one frame."""
        sent: list[bytes] = []
        handler = IsoTpHandler(sent.append, lambda _t: None, IsoTpConfig())
        handler.send(bytes.fromhex("22F190"))
        assert len(sent) == 1
        assert sent[0][0] == 0x03
        assert sent[0][1:4] == bytes.fromhex("22F190")

    def test_padding_fills_to_eight_bytes(self) -> None:
        """Transmitted frames are padded to eight bytes by default."""
        sent: list[bytes] = []
        handler = IsoTpHandler(sent.append, lambda _t: None, IsoTpConfig(padding_byte=0xAA))
        handler.send(b"\x10\x03")
        assert len(sent[0]) == 8
        assert sent[0][3:] == b"\xaa" * 5

    def test_padding_disabled(self) -> None:
        """Padding can be switched off."""
        sent: list[bytes] = []
        handler = IsoTpHandler(sent.append, lambda _t: None, IsoTpConfig(tx_padding=False))
        handler.send(b"\x10\x03")
        assert len(sent[0]) == 3

    def test_round_trip(self) -> None:
        """A single frame payload survives the round trip."""
        first, second = make_pair()
        assert exchange(first, second, bytes.fromhex("22F190")) == bytes.fromhex("22F190")

    def test_empty_payload_rejected(self) -> None:
        """Sending nothing raises."""
        handler = IsoTpHandler(lambda _f: None, lambda _t: None)
        with pytest.raises(ValueError):
            handler.send(b"")


class TestMultiFrame:
    """Segmented transmission with flow control."""

    @pytest.mark.parametrize("size", [8, 20, 63, 100, 500, 1000, 4095])
    def test_round_trip_various_sizes(self, size: int) -> None:
        """Payloads of many sizes are reassembled byte for byte."""
        first, second = make_pair()
        payload = bytes(i & 0xFF for i in range(size))
        assert exchange(first, second, payload) == payload

    def test_block_size_triggers_flow_control(self) -> None:
        """A small block size produces several flow control frames."""
        config = IsoTpConfig(block_size=2)
        first, second = make_pair(config, IsoTpConfig(block_size=2))
        payload = bytes(200)
        assert exchange(first, second, payload) == payload
        assert second.statistics.flow_control_sent > 1
        assert first.statistics.flow_control_received > 1

    def test_unlimited_block_size(self) -> None:
        """Block size zero sends everything after one flow control frame."""
        config = IsoTpConfig(block_size=0)
        first, second = make_pair(config, IsoTpConfig(block_size=0))
        payload = bytes(300)
        assert exchange(first, second, payload) == payload
        assert second.statistics.flow_control_sent == 1

    def test_frame_sequence(self) -> None:
        """The generated frames follow the ISO-TP PCI rules."""
        handler = IsoTpHandler(lambda _f: None, lambda _t: None)
        frames = list(handler.iter_frames(bytes(20)))
        assert frames[0][0] >> 4 == 0x1  # first frame
        assert frames[0][1] == 20  # length
        assert [f[0] for f in frames[1:]] == [0x21, 0x22]

    def test_statistics(self) -> None:
        """The counters reflect the exchange."""
        first, second = make_pair()
        payload = bytes(100)
        exchange(first, second, payload)
        assert first.statistics.messages_sent == 1
        assert second.statistics.messages_received == 1
        assert first.statistics.frames_sent > 1


class TestTimeouts:
    """Timeout behaviour."""

    def test_missing_flow_control_raises(self) -> None:
        """No flow control frame means an N_Bs timeout."""
        handler = IsoTpHandler(
            lambda _f: None, lambda _t: None, IsoTpConfig(n_bs_timeout_ms=50)
        )
        with pytest.raises(CommunicationTimeoutError):
            handler.send(bytes(50))
        assert handler.statistics.timeouts == 1

    def test_receive_timeout_returns_none(self) -> None:
        """Receiving nothing returns ``None`` instead of raising."""
        handler = IsoTpHandler(lambda _f: None, lambda _t: None)
        assert handler.receive(0.05) is None

    def test_overflow_flow_control(self) -> None:
        """An overflow flow status aborts the transmission."""
        responses = [bytes([0x32, 0x00, 0x00])]  # FC with overflow
        handler = IsoTpHandler(
            lambda _f: None,
            lambda _t: responses.pop(0) if responses else None,
            IsoTpConfig(),
        )
        with pytest.raises(FlowControlError):
            handler.send(bytes(50))

    def test_too_many_wait_frames(self) -> None:
        """Endless WAIT frames abort the transmission."""
        handler = IsoTpHandler(
            lambda _f: None,
            lambda _t: bytes([0x31, 0x00, 0x00]),
            IsoTpConfig(wait_frame_limit=3),
        )
        with pytest.raises(FlowControlError):
            handler.send(bytes(50))


class TestCanFD:
    """CAN FD specific behaviour."""

    def test_fd_single_frame_uses_escape(self) -> None:
        """Payloads above seven bytes use the two byte FD PCI."""
        sent: list[bytes] = []
        handler = IsoTpHandler(
            sent.append, lambda _t: None, IsoTpConfig(can_fd=True, max_frame_size=64)
        )
        handler.send(bytes(40))
        assert sent[0][0] == 0x00
        assert sent[0][1] == 40
        assert len(sent[0]) == 48  # padded to a legal FD length

    def test_fd_round_trip(self) -> None:
        """Long payloads survive a CAN FD round trip."""
        config = IsoTpConfig(can_fd=True, max_frame_size=64)
        first, second = make_pair(config, IsoTpConfig(can_fd=True, max_frame_size=64))
        payload = bytes(i & 0xFF for i in range(500))
        assert exchange(first, second, payload) == payload

    @pytest.mark.parametrize(
        ("length", "expected"), [(1, 8), (8, 8), (9, 12), (17, 20), (33, 48), (64, 64), (100, 64)]
    )
    def test_fd_padded_length(self, length: int, expected: int) -> None:
        """FD frames are padded to the next legal DLC."""
        assert fd_padded_length(length) == expected


class TestSeparationTime:
    """STmin encoding."""

    @pytest.mark.parametrize(
        ("value", "encoded"), [(0, 0x00), (1, 0x01), (10, 0x0A), (127, 0x7F), (0.5, 0xF5)]
    )
    def test_encode(self, value: float, encoded: int) -> None:
        """Milliseconds and microseconds encode into the right byte."""
        assert encode_st_min(value) == encoded

    @pytest.mark.parametrize(
        ("encoded", "value"), [(0x00, 0.0), (0x0A, 10.0), (0x7F, 127.0), (0xF1, 0.1), (0xF9, 0.9)]
    )
    def test_decode(self, encoded: int, value: float) -> None:
        """The byte decodes back into milliseconds."""
        assert decode_st_min(encoded) == pytest.approx(value)


class TestExtendedAddressing:
    """Extended addressing formats."""

    def test_address_extension_byte_is_prepended(self) -> None:
        """Extended addressing adds the target address byte."""
        from src.core.enums.protocol_enums import IsoTpAddressingFormat

        sent: list[bytes] = []
        config = IsoTpConfig(
            addressing_format=IsoTpAddressingFormat.EXTENDED_11BIT, target_address=0xF1
        )
        handler = IsoTpHandler(sent.append, lambda _t: None, config)
        handler.send(b"\x10\x03")
        assert sent[0][0] == 0xF1
        assert sent[0][1] == 0x02

    def test_extended_round_trip(self) -> None:
        """Extended addressing survives the round trip."""
        from src.core.enums.protocol_enums import IsoTpAddressingFormat

        config_a = IsoTpConfig(
            addressing_format=IsoTpAddressingFormat.EXTENDED_11BIT, target_address=0xF1
        )
        config_b = IsoTpConfig(
            addressing_format=IsoTpAddressingFormat.EXTENDED_11BIT, target_address=0x33
        )
        first, second = make_pair(config_a, config_b)
        payload = bytes(60)
        assert exchange(first, second, payload) == payload
