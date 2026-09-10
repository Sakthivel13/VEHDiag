"""Vehicle communication interface configuration dialog.

Scans for attached hardware, lets the operator choose the interface, the
channel, the protocol and the identifiers, then produces a
:class:`~src.communication.connection_manager.ConnectionProfile` ready to be
handed to the connection manager. Profiles can be saved and reloaded.

Example:
    >>> from ui.dialogs.vci_config_dialog import (
    ...     BITRATES, default_ids, validate_profile)
    >>> 500000 in BITRATES
    True
    >>> default_ids("CAN")
    (2016, 2024, 2015)
    >>> from src.communication.connection_manager import ConnectionProfile
    >>> validate_profile(ConnectionProfile())
    (True, '')
    >>> validate_profile(ConnectionProfile(tx_id=0x7E0, rx_id=0x7E0))[1]
    'the request and response identifiers must differ'
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.communication.connection_manager import ConnectionProfile
from src.communication.vci_drivers.vci_scanner import DetectedVCI, VCIScanner
from src.core.enums.protocol_enums import ProtocolType
from src.core.enums.vci_enums import VCIType

from ..dpi_scaler import DPIScaler
from ..widgets.scalable_button import ScalableButton
from ..styles.layout_helpers import tune_form

__all__ = [
    "BITRATES",
    "VCIConfigDialog",
    "default_ids",
    "validate_profile",
]

#: Bitrates offered by the drop-down.
BITRATES: tuple[int, ...] = (125_000, 250_000, 500_000, 800_000, 1_000_000)

#: CAN FD data phase bitrates offered by the drop-down.
DATA_BITRATES: tuple[int, ...] = (500_000, 1_000_000, 2_000_000, 4_000_000, 5_000_000)


def default_ids(protocol: str) -> tuple[int, int, int]:
    """Return the default ``(tx, rx, functional)`` identifiers of *protocol*.

    Example:
        >>> default_ids("J1939")[0]
        249
        >>> default_ids("DOIP")
        (3712, 3584, 57343)
    """
    upper = protocol.upper()
    if upper == "J1939":
        return 0xF9, 0x00, 0xFF
    if upper in ("DOIP", "ETHERNET"):
        return 0x0E80, 0x0E00, 0xDFFF
    return 0x7E0, 0x7E8, 0x7DF


def validate_profile(profile: ConnectionProfile) -> tuple[bool, str]:
    """Validate a connection profile before it is used.

    Args:
        profile: The profile built by the dialog.

    Returns:
        ``(is_valid, reason)``; *reason* is empty when the profile is usable.

    Example:
        >>> validate_profile(ConnectionProfile(bitrate=0))[1]
        'the bitrate must be positive'
    """
    if profile.bitrate <= 0:
        return False, "the bitrate must be positive"
    if profile.tx_id == profile.rx_id:
        return False, "the request and response identifiers must differ"
    limit = 0x1FFFFFFF if profile.extended_id else 0x7FF
    for label, value in (("request", profile.tx_id), ("response", profile.rx_id)):
        if not 0 <= value <= limit:
            return False, f"the {label} identifier does not fit in the selected ID width"
    if profile.protocol in (ProtocolType.DOIP,) and not profile.options.get("host"):
        return False, "DoIP requires a host address"
    return True, ""


class VCIConfigDialog(QDialog):
    """Configures the vehicle communication interface.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        profile: Profile pre-loaded into the editors.
        scanner: Scanner used by :meth:`scan`.

    Attributes:
        detected: The interfaces found by the last scan.
    """

    #: Emitted with the accepted profile.
    profile_accepted = Signal(object)
    #: Emitted with the detected interfaces after a scan.
    devices_detected = Signal(list)

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        profile: ConnectionProfile | None = None,
        scanner: VCIScanner | None = None,
    ) -> None:
        """Build the hardware, protocol and identifier sections."""
        super().__init__(parent)
        self.scaler = scaler or DPIScaler()
        self.scanner = scanner or VCIScanner()
        self.detected: list[DetectedVCI] = []

        self.setWindowTitle("Configure the VCI")
        self.setModal(True)
        self.setMinimumWidth(self.scaler.px(560))

        self.type_box = QComboBox(self)
        for vci in VCIType:
            self.type_box.addItem(vci.value, vci.value)
        self.device_box = QComboBox(self)
        self.channel_field = QLineEdit("0", self)
        self.protocol_box = QComboBox(self)
        for protocol in ProtocolType:
            self.protocol_box.addItem(protocol.value, protocol.value)
        self.protocol_box.currentIndexChanged.connect(self._on_protocol_changed)

        self.bitrate_box = QComboBox(self)
        self.bitrate_box.setEditable(True)
        self.bitrate_box.addItems([str(rate) for rate in BITRATES])
        self.bitrate_box.setCurrentText("500000")
        self.data_bitrate_box = QComboBox(self)
        self.data_bitrate_box.setEditable(True)
        self.data_bitrate_box.addItems([str(rate) for rate in DATA_BITRATES])
        self.data_bitrate_box.setCurrentText("2000000")

        self.tx_field = QLineEdit("7E0", self)
        self.rx_field = QLineEdit("7E8", self)
        self.functional_field = QLineEdit("7DF", self)
        self.extended_box = QCheckBox("Use 29-bit identifiers", self)
        self.host_field = QLineEdit("", self)
        self.host_field.setPlaceholderText("DoIP host, e.g. 192.168.0.10")
        self.port_spin = QSpinBox(self)
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(13400)

        self.scan_button = ScalableButton("Scan", "search", self, self.scaler)
        self.scan_button.clicked.connect(self.scan)
        self.load_button = ScalableButton("Load profile", "folder_open", self, self.scaler)
        self.load_button.clicked.connect(self.load_dialog)
        self.save_button = ScalableButton("Save profile", "save", self, self.scaler)
        self.save_button.clicked.connect(self.save_dialog)

        self.status_label = QLabel("no scan performed", self)
        self.status_label.setProperty("role", "secondary")
        self.status_label.setWordWrap(True)

        hardware = QGroupBox("Hardware", self)
        hardware_form = QFormLayout(hardware)
        tune_form(hardware_form, self.scaler)
        hardware_form.addRow("Interface type:", self.type_box)
        hardware_form.addRow("Device:", self.device_box)
        hardware_form.addRow("Channel:", self.channel_field)

        link = QGroupBox("Link", self)
        link_form = QFormLayout(link)
        tune_form(link_form, self.scaler)
        link_form.addRow("Protocol:", self.protocol_box)
        link_form.addRow("Bitrate:", self.bitrate_box)
        link_form.addRow("Data bitrate (FD):", self.data_bitrate_box)
        link_form.addRow("", self.extended_box)

        addressing = QGroupBox("Addressing", self)
        addressing_form = QFormLayout(addressing)
        tune_form(addressing_form, self.scaler)
        addressing_form.addRow("Request ID (hex):", self.tx_field)
        addressing_form.addRow("Response ID (hex):", self.rx_field)
        addressing_form.addRow("Functional ID (hex):", self.functional_field)
        addressing_form.addRow("DoIP host:", self.host_field)
        addressing_form.addRow("DoIP port:", self.port_spin)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(self.scaler.spacing(4))
        toolbar.addWidget(self.scan_button)
        toolbar.addStretch(1)
        toolbar.addWidget(self.load_button)
        toolbar.addWidget(self.save_button)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        self.buttons.accepted.connect(self._on_accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setSpacing(self.scaler.spacing(8))
        layout.addLayout(toolbar)
        layout.addWidget(hardware)
        layout.addWidget(link)
        layout.addWidget(addressing)
        layout.addWidget(self.status_label)
        layout.addWidget(self.buttons)

        if profile is not None:
            self.set_profile(profile)
        self._on_protocol_changed(self.protocol_box.currentIndex())

    # -- API -----------------------------------------------------------------
    def scan(self) -> list[DetectedVCI]:
        """Scan for attached interfaces and fill the device drop-down."""
        self.detected = self.scanner.scan(include_virtual=True)
        self.device_box.clear()
        for device in self.detected:
            self.device_box.addItem(device.label, device.channel)
        self.status_label.setText(f"{len(self.detected)} interface(s) detected")
        self.devices_detected.emit(list(self.detected))
        return self.detected

    def profile(self) -> ConnectionProfile:
        """Return the :class:`ConnectionProfile` described by the editors."""
        channel_text = self.channel_field.text().strip()
        channel: int | str = int(channel_text) if channel_text.isdigit() else channel_text
        return ConnectionProfile(
            name="Dialog profile",
            vci_type=VCIType(self.type_box.currentText()),
            channel=channel,
            protocol=ProtocolType(self.protocol_box.currentText()),
            bitrate=self._int(self.bitrate_box.currentText(), 500_000),
            data_bitrate=self._int(self.data_bitrate_box.currentText(), 2_000_000),
            tx_id=self._hex(self.tx_field.text(), 0x7E0),
            rx_id=self._hex(self.rx_field.text(), 0x7E8),
            functional_id=self._hex(self.functional_field.text(), 0x7DF),
            extended_id=self.extended_box.isChecked(),
            options={"host": self.host_field.text().strip(), "port": self.port_spin.value()},
        )

    def set_profile(self, profile: ConnectionProfile) -> None:
        """Load *profile* into the editors."""
        index = self.type_box.findData(profile.vci_type.value)
        if index >= 0:
            self.type_box.setCurrentIndex(index)
        index = self.protocol_box.findData(profile.protocol.value)
        if index >= 0:
            self.protocol_box.setCurrentIndex(index)
        self.channel_field.setText(str(profile.channel))
        self.bitrate_box.setCurrentText(str(profile.bitrate))
        self.data_bitrate_box.setCurrentText(str(profile.data_bitrate))
        self.tx_field.setText(f"{profile.tx_id:X}")
        self.rx_field.setText(f"{profile.rx_id:X}")
        self.functional_field.setText(f"{profile.functional_id:X}")
        self.extended_box.setChecked(profile.extended_id)
        self.host_field.setText(str(profile.options.get("host", "")))
        self.port_spin.setValue(int(profile.options.get("port", 13400)))

    def is_valid(self) -> bool:
        """Return ``True`` when the current profile can be used."""
        return validate_profile(self.profile())[0]

    def save(self, path: str | Path) -> Path:
        """Write the current profile to *path* as YAML."""
        target = Path(path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            yaml.safe_dump(self.profile().to_dict(), sort_keys=False), encoding="utf-8"
        )
        return target

    def load(self, path: str | Path) -> ConnectionProfile:
        """Load a profile from the YAML file at *path*."""
        data = yaml.safe_load(Path(path).expanduser().read_text(encoding="utf-8")) or {}
        profile = ConnectionProfile.from_dict(data)
        self.set_profile(profile)
        return profile

    def save_dialog(self) -> Path | None:
        """Ask where to save the profile and write it."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Save the VCI profile", str(Path.home()), "YAML files (*.yaml *.yml)"
        )
        return self.save(path) if path else None

    def load_dialog(self) -> ConnectionProfile | None:
        """Ask for a profile file and load it."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Load a VCI profile", str(Path.home()), "YAML files (*.yaml *.yml)"
        )
        return self.load(path) if path else None

    # -- internals ------------------------------------------------------------
    @staticmethod
    def _int(text: str, fallback: int) -> int:
        """Parse a decimal integer, falling back to *fallback*."""
        try:
            return int(text.strip())
        except ValueError:
            return fallback

    @staticmethod
    def _hex(text: str, fallback: int) -> int:
        """Parse a hexadecimal identifier, falling back to *fallback*."""
        try:
            return int(text.strip().lower().removeprefix("0x"), 16)
        except ValueError:
            return fallback

    def _on_protocol_changed(self, _index: int) -> None:
        """Pre-fill the identifiers and toggle the DoIP fields."""
        protocol = self.protocol_box.currentText()
        tx, rx, functional = default_ids(protocol)
        self.tx_field.setText(f"{tx:X}")
        self.rx_field.setText(f"{rx:X}")
        self.functional_field.setText(f"{functional:X}")
        is_doip = protocol.upper() in ("DOIP", "ETHERNET")
        self.host_field.setEnabled(is_doip)
        self.port_spin.setEnabled(is_doip)
        self.data_bitrate_box.setEnabled(protocol.upper() in ("CAN_FD", "CANFD"))

    def _on_accept(self) -> None:
        """Validate the profile, then close the dialog."""
        profile = self.profile()
        valid, reason = validate_profile(profile)
        if not valid:
            self.status_label.setText(reason)
            self.status_label.setProperty("state", "error")
            return
        self.profile_accepted.emit(profile)
        self.accept()
