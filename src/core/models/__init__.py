"""Data models shared across the Vehicle Diagnostics Platform."""
from __future__ import annotations

from .did_model import DIDDefinition, DIDRegistry, DIDValue
from .dtc_model import (
    DTC,
    DTC_STATUS_BITS,
    DTCExtendedRecord,
    DTCReport,
    DTCSnapshotRecord,
    DTCStatus,
)
from .ecu_model import ECU, ECUAddressing, ECUIdentification
from .file_transfer_model import MemorySegment, TransferFile, TransferProgress
from .log_entry_model import LogCategory, LogEntry, LogLevel
from .message_model import BusMessage, DiagnosticMessage
from .response_data_model import DiagnosticResponse
from .session_model import SessionState, SessionTiming, SessionTransition
from .test_sequence_model import ExecutionMode, TestResult, TestSequence, TestStatus, TestStep
from .vci_model import VCIChannelConfig, VCIDeviceInfo, VCIStatus

__all__ = [
    "BusMessage",
    "DIDDefinition",
    "DIDRegistry",
    "DIDValue",
    "DTC",
    "DTCExtendedRecord",
    "DTCReport",
    "DTCSnapshotRecord",
    "DTCStatus",
    "DTC_STATUS_BITS",
    "DiagnosticMessage",
    "DiagnosticResponse",
    "ECU",
    "ECUAddressing",
    "ECUIdentification",
    "ExecutionMode",
    "LogCategory",
    "LogEntry",
    "LogLevel",
    "MemorySegment",
    "SessionState",
    "SessionTiming",
    "SessionTransition",
    "TestResult",
    "TestSequence",
    "TestStatus",
    "TestStep",
    "TransferFile",
    "TransferProgress",
    "VCIChannelConfig",
    "VCIDeviceInfo",
    "VCIStatus",
]
