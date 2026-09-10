"""Shared utility helpers for the Vehicle Diagnostics Platform."""
from __future__ import annotations

from .byte_utils import (
    bytes_to_ascii,
    bytes_to_binary,
    bytes_to_hex,
    bytes_to_int,
    chunk_bytes,
    clean_hex,
    extract_bits,
    hex_dump,
    hex_to_bytes,
    int_to_bytes,
    pad_bytes,
    split_did,
    swap_endianness,
)
from .checksum_calculator import calculate, crc16_ccitt, crc32, sha256, verify
from .file_utils import ensure_dir, human_size, load_yaml, save_yaml
from .observer import Observable
from .platform_utils import app_data_dir, is_linux, is_macos, is_windows, system_info
from .singleton import Singleton
from .threading_utils import Result, StoppableThread, ThreadSafeCounter, synchronized
from .timer_utils import Deadline, PeriodicTimer, Stopwatch, monotonic_ms, now_us
from .validation_utils import validate_can_id, validate_did, validate_dtc, validate_hex_string

__all__ = [
    "Deadline",
    "Observable",
    "PeriodicTimer",
    "Result",
    "Singleton",
    "Stopwatch",
    "StoppableThread",
    "ThreadSafeCounter",
    "app_data_dir",
    "bytes_to_ascii",
    "bytes_to_binary",
    "bytes_to_hex",
    "bytes_to_int",
    "calculate",
    "chunk_bytes",
    "clean_hex",
    "crc16_ccitt",
    "crc32",
    "ensure_dir",
    "extract_bits",
    "hex_dump",
    "hex_to_bytes",
    "human_size",
    "int_to_bytes",
    "is_linux",
    "is_macos",
    "is_windows",
    "load_yaml",
    "monotonic_ms",
    "now_us",
    "pad_bytes",
    "save_yaml",
    "sha256",
    "split_did",
    "swap_endianness",
    "synchronized",
    "system_info",
    "validate_can_id",
    "validate_did",
    "validate_dtc",
    "validate_hex_string",
    "verify",
]
