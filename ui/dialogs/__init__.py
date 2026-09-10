"""Application dialogs."""
from __future__ import annotations

from .about_dialog import AboutDialog
from .confirmation_dialog import ConfirmationDialog
from .ecu_identification_dialog import ECUIdentificationDialog
from .error_dialog import ErrorDialog
from .file_transfer_dialog import FileTransferDialog
from .preferences_dialog import PreferencesDialog
from .progress_dialog import ProgressDialog
from .report_generator_dialog import ReportData, ReportGeneratorDialog
from .vci_config_dialog import VCIConfigDialog

__all__ = [
    "AboutDialog",
    "ConfirmationDialog",
    "ECUIdentificationDialog",
    "ErrorDialog",
    "FileTransferDialog",
    "PreferencesDialog",
    "ProgressDialog",
    "ReportData",
    "ReportGeneratorDialog",
    "VCIConfigDialog",
]
