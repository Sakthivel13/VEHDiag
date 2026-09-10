"""CAN bit timing calculation helpers."""
from __future__ import annotations

from dataclasses import dataclass

#: Bitrates offered in the connection panel.
STANDARD_BITRATES: tuple[int, ...] = (10_000, 20_000, 50_000, 100_000, 125_000, 250_000, 500_000, 800_000, 1_000_000)

#: CAN FD data phase bitrates offered in the connection panel.
FD_DATA_BITRATES: tuple[int, ...] = (1_000_000, 2_000_000, 4_000_000, 5_000_000, 8_000_000)


@dataclass(slots=True)
class BitTiming:
    """Concrete bit timing register values for a controller.

    Attributes:
        bitrate: Resulting bitrate in bit/s.
        brp: Baud rate prescaler.
        tseg1: Time segment 1 in time quanta (includes the propagation segment).
        tseg2: Time segment 2 in time quanta.
        sjw: Synchronisation jump width in time quanta.
        clock_hz: Controller clock used for the calculation.
    """

    bitrate: int
    brp: int
    tseg1: int
    tseg2: int
    sjw: int
    clock_hz: int

    @property
    def total_quanta(self) -> int:
        """Return the number of time quanta per bit (sync + tseg1 + tseg2)."""
        return 1 + self.tseg1 + self.tseg2

    @property
    def sample_point(self) -> float:
        """Return the sample point as a fraction of the bit time."""
        return (1 + self.tseg1) / self.total_quanta

    @property
    def actual_bitrate(self) -> float:
        """Return the bitrate the register values really produce."""
        return self.clock_hz / (self.brp * self.total_quanta)

    @property
    def error_percent(self) -> float:
        """Return the relative deviation from the requested bitrate."""
        return abs(self.actual_bitrate - self.bitrate) / self.bitrate * 100.0


def calculate_bit_timing(
    bitrate: int,
    clock_hz: int = 80_000_000,
    sample_point: float = 0.875,
    max_brp: int = 64,
    max_tseg1: int = 16,
    max_tseg2: int = 8,
) -> BitTiming:
    """Compute bit timing registers approximating *bitrate*.

    Args:
        bitrate: Desired bitrate in bit/s.
        clock_hz: Controller clock frequency.
        sample_point: Desired sample point as a fraction (0..1).
        max_brp: Largest supported prescaler.
        max_tseg1: Largest supported time segment 1.
        max_tseg2: Largest supported time segment 2.

    Returns:
        The timing whose bitrate error and sample point deviation are smallest.

    Raises:
        ValueError: No combination produced a usable timing.

    Example:
        >>> t = calculate_bit_timing(500_000, clock_hz=80_000_000)
        >>> round(t.actual_bitrate)
        500000
    """
    best: BitTiming | None = None
    best_score = float("inf")
    for brp in range(1, max_brp + 1):
        total = clock_hz / (brp * bitrate)
        quanta = int(round(total))
        if quanta < 4 or quanta > 1 + max_tseg1 + max_tseg2:
            continue
        tseg1 = int(round(quanta * sample_point)) - 1
        tseg1 = max(1, min(max_tseg1, tseg1))
        tseg2 = quanta - 1 - tseg1
        if not 1 <= tseg2 <= max_tseg2:
            continue
        timing = BitTiming(
            bitrate=bitrate,
            brp=brp,
            tseg1=tseg1,
            tseg2=tseg2,
            sjw=min(4, tseg2),
            clock_hz=clock_hz,
        )
        score = timing.error_percent * 10 + abs(timing.sample_point - sample_point) * 100
        if score < best_score:
            best, best_score = timing, score
    if best is None:
        raise ValueError(f"no bit timing found for {bitrate} bit/s at {clock_hz} Hz")
    return best


def nominal_bit_time_us(bitrate: int) -> float:
    """Return the duration of one bit in microseconds."""
    return 1_000_000.0 / bitrate


def frame_duration_us(bitrate: int, data_length: int, extended: bool = False) -> float:
    """Estimate the time one CAN frame occupies the bus, worst case stuffing.

    Example:
        >>> round(frame_duration_us(500_000, 8))
        222
    """
    overhead_bits = 67 if extended else 47
    bits = overhead_bits + data_length * 8
    bits *= 1.2  # allow for bit stuffing
    return bits * nominal_bit_time_us(bitrate)


def bus_load_percent(bitrate: int, frames_per_second: float, average_dlc: int = 8) -> float:
    """Estimate the bus load produced by a message rate."""
    per_frame_us = frame_duration_us(bitrate, average_dlc)
    return min(100.0, frames_per_second * per_frame_us / 10_000.0)


__all__ = [
    "STANDARD_BITRATES",
    "FD_DATA_BITRATES",
    "BitTiming",
    "calculate_bit_timing",
    "nominal_bit_time_us",
    "frame_duration_us",
    "bus_load_percent",
]
