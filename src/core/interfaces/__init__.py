"""Abstract interfaces decoupling the platform layers."""
from __future__ import annotations

from .i_data_converter import IDataConverter
from .i_diagnostic_service import IDiagnosticService
from .i_file_parser import IFileParser
from .i_logger import ILogger
from .i_plugin import IPlugin
from .i_protocol_handler import IProtocolHandler
from .i_test_runner import ITestRunner
from .i_vci_driver import IVCIDriver

__all__ = [
    "IDataConverter",
    "IDiagnosticService",
    "IFileParser",
    "ILogger",
    "IPlugin",
    "IProtocolHandler",
    "ITestRunner",
    "IVCIDriver",
]
