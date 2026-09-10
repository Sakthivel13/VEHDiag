"""Protocol and timing settings page.

Covers the CAN / CAN FD bit timing, the ISO 15765-2 parameters, the DoIP
endpoint, the K-Line initialisation and the LIN schedule, plus the UDS client
timing (P2, P2*, S3) that governs every request.

Example:
    >>> from ui.panels.settings_panel.protocol_settings import SETTINGS, paths
    >>> "protocols.isotp.block_size" in paths()
    True
    >>> [s.suffix for s in SETTINGS if s.path == "protocols.isotp.st_min_ms"]
    [' ms']
"""
from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QWidget

from src.core.configuration_manager import ConfigurationManager

from ...dpi_scaler import DPIScaler
from .general_settings import SettingSpec, SettingsPage

__all__ = ["ISOTP_SETTINGS", "ProtocolSettingsPage", "SETTINGS", "paths"]

#: ISO 15765-2 transport settings, exposed separately for the VCI dialog.
ISOTP_SETTINGS: tuple[SettingSpec, ...] = (
    SettingSpec(
        "protocols.isotp.block_size",
        "Block size (BS)",
        "int",
        minimum=0,
        maximum=255,
        tooltip="Number of consecutive frames between two flow control frames; 0 means unlimited.",
    ),
    SettingSpec(
        "protocols.isotp.st_min_ms",
        "Separation time (STmin)",
        "int",
        minimum=0,
        maximum=127,
        suffix=" ms",
    ),
    SettingSpec(
        "protocols.isotp.n_bs_timeout_ms",
        "N_Bs timeout",
        "int",
        minimum=100,
        maximum=10000,
        suffix=" ms",
    ),
    SettingSpec(
        "protocols.isotp.n_cr_timeout_ms",
        "N_Cr timeout",
        "int",
        minimum=100,
        maximum=10000,
        suffix=" ms",
    ),
    SettingSpec("protocols.isotp.padding_byte", "Padding byte", "int", minimum=0, maximum=255),
)

#: Every setting shown on the protocol page.
SETTINGS: tuple[SettingSpec, ...] = (
    SettingSpec(
        "protocols.can.bitrate", "CAN bitrate", "int", minimum=5000, maximum=1_000_000,
        suffix=" bit/s",
    ),
    SettingSpec(
        "protocols.can.data_bitrate", "CAN FD data bitrate", "int",
        minimum=5000, maximum=8_000_000, suffix=" bit/s",
    ),
    SettingSpec("protocols.can.extended_id", "Use 29-bit identifiers", "bool"),
    SettingSpec("protocols.can.fd_enabled", "Enable CAN FD", "bool"),
    SettingSpec("protocols.can.padding_enabled", "Pad CAN frames", "bool"),
    SettingSpec(
        "protocols.can.tx_id", "Request identifier", "int", minimum=0, maximum=0x1FFFFFFF
    ),
    SettingSpec(
        "protocols.can.rx_id", "Response identifier", "int", minimum=0, maximum=0x1FFFFFFF
    ),
    *ISOTP_SETTINGS,
    SettingSpec("protocols.doip.host", "DoIP host"),
    SettingSpec("protocols.doip.port", "DoIP port", "int", minimum=1, maximum=65535),
    SettingSpec(
        "protocols.doip.logical_address", "DoIP logical address", "int",
        minimum=0, maximum=0xFFFF,
    ),
    SettingSpec(
        "protocols.kline.baudrate", "K-Line baudrate", "int",
        minimum=1200, maximum=115200, suffix=" baud",
    ),
    SettingSpec(
        "protocols.kline.init_type", "K-Line initialisation", "choice",
        choices=("FAST", "SLOW_5BAUD", "NONE"),
    ),
    SettingSpec(
        "protocols.lin.baudrate", "LIN baudrate", "int",
        minimum=1200, maximum=20000, suffix=" baud",
    ),
    SettingSpec(
        "diagnostics.p2_client_ms", "P2 client", "int", minimum=50, maximum=10000, suffix=" ms"
    ),
    SettingSpec(
        "diagnostics.p2_star_client_ms", "P2* client", "int",
        minimum=500, maximum=60000, suffix=" ms",
    ),
    SettingSpec(
        "diagnostics.s3_client_ms", "S3 client", "int",
        minimum=500, maximum=30000, suffix=" ms",
    ),
)


def paths() -> list[str]:
    """Return every configuration path edited by this page.

    Example:
        >>> "protocols.doip.port" in paths()
        True
    """
    return [spec.path for spec in SETTINGS]


class ProtocolSettingsPage(SettingsPage):
    """The protocol and timing settings page.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        config: Configuration manager backing the editors.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        config: ConfigurationManager | None = None,
    ) -> None:
        """Build the page from :data:`SETTINGS`."""
        super().__init__(SETTINGS, "Protocols and timing", parent, scaler, config)
