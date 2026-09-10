"""Shared Utilities."""
import time
import yaml
from contextlib import contextmanager


class BitUtils:
    @staticmethod
    def get_bit(byte_array: bytes, bit_idx: int) -> int:
        byte_idx = bit_idx // 8
        bit_in_byte = bit_idx % 8
        if byte_idx >= len(byte_array):
            return 0
        return (byte_array[byte_idx] >> bit_in_byte) & 1


class EndianUtils:
    @staticmethod
    def to_int_le(data: bytes) -> int:
        return int.from_bytes(data, "little")

    @staticmethod
    def to_int_be(data: bytes) -> int:
        return int.from_bytes(data, "big")


class TimeUtils:
    @staticmethod
    def now():
        return time.time()


@contextmanager
def Profiler(name: str):
    start = time.time()
    yield
    end = time.time()
    print(f"[PROFILE] {name}: {end-start:.6f}s")


class ConfigLoader:
    @staticmethod
    def load_config(path: str):
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)


class PerformanceMonitor:
    def __init__(self):
        self.metrics = {}

    def record(self, key, value):
        self.metrics.setdefault(key, []).append(value)

    def get(self, key):
        return self.metrics.get(key, [])