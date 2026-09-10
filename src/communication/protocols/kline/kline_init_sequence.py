"""K-Line initialisation sequences (5-baud and fast init)."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from ....core.exceptions import ProtocolError, TimingError
from .kline_timing import FAST_INIT_HIGH_MS, FAST_INIT_LOW_MS, FIVE_BAUD_BIT_MS, KLineTiming

_logger = logging.getLogger(__name__)

#: Address byte used to address all OBD ECUs.
OBD_ADDRESS = 0x33


@dataclass(slots=True)
class InitResult:
    """Outcome of an initialisation attempt.

    Attributes:
        success: ``True`` when the ECU answered correctly.
        key_bytes: The two keyword bytes reported by the ECU.
        message: Human readable description of the outcome.
        elapsed_ms: Duration of the whole sequence.
    """

    success: bool
    key_bytes: tuple[int, int] = (0x00, 0x00)
    message: str = ""
    elapsed_ms: float = 0.0

    @property
    def protocol_hint(self) -> str:
        """Return the protocol implied by the keyword bytes."""
        first, second = self.key_bytes
        if (first, second) == (0x08, 0x08):
            return "ISO 9141-2 (5 baud)"
        if (first, second) == (0x94, 0x94):
            return "ISO 9141-2 (fast timing)"
        if first in (0x8F, 0xEF, 0x6B):
            return "ISO 14230-4 KWP2000"
        return "unknown"


def five_baud_init(
    serial_port: Any,
    address: int = OBD_ADDRESS,
    timing: KLineTiming | None = None,
) -> InitResult:
    """Perform the ISO 9141-2 five baud initialisation.

    The address byte is bit-banged at 5 baud by toggling the break condition,
    then the ECU answers with the sync byte ``0x55`` and two keyword bytes. The
    tester echoes the inverted second keyword byte and the ECU replies with the
    inverted address byte.

    Args:
        serial_port: An open :class:`serial.Serial` compatible object.
        address: Address byte to send (``0x33`` for OBD).
        timing: Timing parameters to honour.

    Returns:
        The :class:`InitResult` describing the handshake.

    Raises:
        TimingError: The ECU did not answer within W1..W4.
        ProtocolError: The sync byte was not ``0x55``.
    """
    timing = timing or KLineTiming.iso9141()
    start = time.perf_counter()
    bit_time = FIVE_BAUD_BIT_MS / 1000.0

    serial_port.break_condition = True  # start bit
    time.sleep(bit_time)
    for index in range(8):
        serial_port.break_condition = not bool((address >> index) & 0x01)
        time.sleep(bit_time)
    serial_port.break_condition = False  # stop bit
    time.sleep(bit_time)
    serial_port.reset_input_buffer()

    deadline = time.perf_counter() + timing.w1_ms / 1000.0
    sync = b""
    while time.perf_counter() < deadline and not sync:
        sync = serial_port.read(1)
    if not sync:
        raise TimingError("no sync byte received during five baud init (W1 timeout)")
    if sync[0] != 0x55:
        raise ProtocolError(f"unexpected sync byte 0x{sync[0]:02X}, expected 0x55")

    key1 = serial_port.read(1)
    key2 = serial_port.read(1)
    if len(key1) != 1 or len(key2) != 1:
        raise TimingError("keyword bytes were not received (W2/W3 timeout)")

    time.sleep(timing.w4_ms / 1000.0)
    serial_port.write(bytes([(~key2[0]) & 0xFF]))
    echo = serial_port.read(1)
    if len(echo) == 1 and echo[0] == ((~address) & 0xFF):
        message = "five baud init successful"
        success = True
    else:
        message = "ECU did not confirm the inverted address byte"
        success = False
    return InitResult(
        success=success,
        key_bytes=(key1[0], key2[0]),
        message=message,
        elapsed_ms=(time.perf_counter() - start) * 1000.0,
    )


def fast_init(
    serial_port: Any,
    start_communication: bytes = bytes.fromhex("C1 33 F1 81"),
    timing: KLineTiming | None = None,
) -> InitResult:
    """Perform the ISO 14230 fast initialisation.

    A 25 ms low pulse followed by a 25 ms high pulse is generated on the K-Line,
    then the ``StartCommunication`` request is transmitted.

    Args:
        serial_port: An open :class:`serial.Serial` compatible object.
        start_communication: Request sent after the wake-up pattern; the
            checksum is appended automatically.
        timing: Timing parameters to honour.

    Returns:
        The :class:`InitResult` describing the handshake.
    """
    from ....utils.checksum_calculator import sum8

    timing = timing or KLineTiming.kwp2000_fast()
    start = time.perf_counter()

    serial_port.break_condition = True
    time.sleep(FAST_INIT_LOW_MS / 1000.0)
    serial_port.break_condition = False
    time.sleep(FAST_INIT_HIGH_MS / 1000.0)

    request = start_communication + bytes([sum8(start_communication)])
    serial_port.reset_input_buffer()
    serial_port.write(request)
    serial_port.read(len(request))  # discard the local echo

    response = serial_port.read(16)
    success = len(response) >= 4
    key_bytes = (response[3], response[4]) if len(response) >= 5 else (0x00, 0x00)
    return InitResult(
        success=success,
        key_bytes=key_bytes,
        message="fast init successful" if success else "no StartCommunication response",
        elapsed_ms=(time.perf_counter() - start) * 1000.0,
    )


__all__ = ["InitResult", "five_baud_init", "fast_init", "OBD_ADDRESS"]
