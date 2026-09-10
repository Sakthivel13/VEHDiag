"""Exception hierarchy for the Vehicle Diagnostics Platform.

All exceptions derive from :class:`VDPError`, which carries a human readable
message plus an optional ``details`` mapping used by the error dialog to show
technical context.
"""
from __future__ import annotations

from .communication_exceptions import (
    BufferOverflowError,
    BusError,
    CommunicationError,
    CommunicationTimeoutError,
    NotConnectedError,
    SendError,
    VDPError,
)
from .diagnostic_exceptions import (
    DiagnosticError,
    InvalidResponseError,
    NegativeResponseError,
    RequestValidationError,
    SecurityAccessDeniedError,
    ServiceNotSupportedError,
    SessionNotSupportedError,
    TransferError,
)
from .file_exceptions import (
    ChecksumMismatchError,
    EmptyFileError,
    FileError,
    FormatNotSupportedError,
    ParseError,
)
from .protocol_exceptions import (
    ChecksumError,
    FlowControlError,
    FramingError,
    IsoTpError,
    ProtocolError,
    SequenceNumberError,
    TimingError,
    UnsupportedProtocolError,
)
from .ui_exceptions import (
    InvalidUserInputError,
    ResourceNotFoundError,
    ThemeLoadError,
    UIError,
    WidgetInitializationError,
)
from .vci_exceptions import (
    ChannelNotAvailableError,
    ConnectionFailedError,
    DriverNotFoundError,
    HardwareNotDetectedError,
    UnsupportedCapabilityError,
    VCIError,
)

__all__ = [
    "BufferOverflowError",
    "BusError",
    "ChannelNotAvailableError",
    "ChecksumError",
    "ChecksumMismatchError",
    "CommunicationError",
    "CommunicationTimeoutError",
    "ConnectionFailedError",
    "DiagnosticError",
    "DriverNotFoundError",
    "EmptyFileError",
    "FileError",
    "FlowControlError",
    "FormatNotSupportedError",
    "FramingError",
    "HardwareNotDetectedError",
    "InvalidResponseError",
    "InvalidUserInputError",
    "IsoTpError",
    "NegativeResponseError",
    "NotConnectedError",
    "ParseError",
    "ProtocolError",
    "RequestValidationError",
    "ResourceNotFoundError",
    "SecurityAccessDeniedError",
    "SendError",
    "SequenceNumberError",
    "ServiceNotSupportedError",
    "SessionNotSupportedError",
    "ThemeLoadError",
    "TimingError",
    "TransferError",
    "UIError",
    "UnsupportedCapabilityError",
    "UnsupportedProtocolError",
    "VCIError",
    "VDPError",
    "WidgetInitializationError",
]
