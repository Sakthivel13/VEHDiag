"""VCI connection panel with protocol specific configuration."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.communication.connection_manager import ConnectionProfile
from src.communication.vci_drivers.vci_scanner import DetectedVCI, VCIScanner
from src.core.enums.protocol_enums import ConnectionState, ProtocolType
from src.core.enums.vci_enums import VCIType

from ...dpi_scaler import DPIScaler
from ...widgets.connection_status_widget import ConnectionStatusWidget
from ...widgets.hex_input_field import HexInputField
from ...widgets.responsive_widget import ResponsiveWidget
from ...widgets.scalable_button import ScalableButton
from ...widgets.scalable_label import HeadingLabel

#: Bitrates offered in the CAN configuration.
BITRATES: tuple[int, ...] = (125_000, 250_000, 500_000, 800_000, 1_000_000)


class ConnectionPanel(ResponsiveWidget):
    """Lets the operator choose the VCI, the protocol and the addressing.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
    """

    #: Emitted with the profile when the operator presses *Connect*.
    connect_requested = Signal(object)
    #: Emitted when the operator presses *Disconnect*.
    disconnect_requested = Signal()
    #: Emitted when the operator asks for a hardware scan.
    scan_requested = Signal()
    #: Emitted with the profile the operator wants to save.
    profile_save_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Build the VCI, protocol and protocol-specific sections."""
        super().__init__(parent, scaler)
        self.detected: list[DetectedVCI] = []

        # -- VCI selection ---------------------------------------------------
        self.vci_box = QComboBox(self)
        for vci_type in VCIType:
            self.vci_box.addItem(vci_type.display_name, vci_type.value)
        self.vci_box.setCurrentIndex(self.vci_box.findData(VCIType.VIRTUAL.value))
        self.device_box = QComboBox(self)
        self.device_box.addItem("Default device", 0)
        self.channel_box = QComboBox(self)
        # Editable: SocketCAN channels are kernel interface names, and no
        # fixed list can know whether the bench uses can0, vcan0 or slcan0.
        self.channel_box.setEditable(True)
        self.channel_box.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.vci_box.currentIndexChanged.connect(self._on_vci_changed)
        self._populate_channels()
        self.scan_button = ScalableButton("Scan devices", "refresh", self, self.scaler)
        self.scan_button.clicked.connect(self.scan_requested.emit)

        # -- protocol --------------------------------------------------------
        self.protocol_box = QComboBox(self)
        for protocol in ProtocolType:
            if protocol is ProtocolType.VIRTUAL:
                continue
            self.protocol_box.addItem(protocol.display_name, protocol.value)
        self.protocol_box.currentIndexChanged.connect(self._on_protocol_changed)

        self.stack = QStackedWidget(self)
        self.can_page = self._build_can_page()
        self.doip_page = self._build_doip_page()
        self.serial_page = self._build_serial_page()
        self.j1939_page = self._build_j1939_page()
        for page in (self.can_page, self.doip_page, self.serial_page, self.j1939_page):
            self.stack.addWidget(page)

        # -- actions ---------------------------------------------------------
        self.connect_button = ScalableButton("Connect", "connect", self, self.scaler, accent=True)
        self.connect_button.clicked.connect(self._on_connect)
        self.disconnect_button = ScalableButton("Disconnect", "disconnect", self, self.scaler)
        self.disconnect_button.clicked.connect(self.disconnect_requested.emit)
        self.disconnect_button.setEnabled(False)
        self.save_button = ScalableButton("Save profile", "save", self, self.scaler)
        self.save_button.clicked.connect(lambda: self.profile_save_requested.emit(self.profile()))
        self.status = ConnectionStatusWidget(self, self.scaler)

        vci_box = QGroupBox("VCI hardware", self)
        vci_layout = QGridLayout(vci_box)
        vci_layout.setSpacing(self.spacing(8))
        vci_layout.addWidget(QLabel("Type:", self), 0, 0)
        vci_layout.addWidget(self.vci_box, 0, 1)
        vci_layout.addWidget(self.scan_button, 0, 2)
        vci_layout.addWidget(QLabel("Device:", self), 1, 0)
        vci_layout.addWidget(self.device_box, 1, 1, 1, 2)
        vci_layout.addWidget(QLabel("Channel:", self), 2, 0)
        vci_layout.addWidget(self.channel_box, 2, 1)

        protocol_box = QGroupBox("Protocol", self)
        protocol_layout = QVBoxLayout(protocol_box)
        protocol_layout.setSpacing(self.spacing(8))
        protocol_layout.addWidget(self.protocol_box)
        protocol_layout.addWidget(self.stack)

        actions = QHBoxLayout()
        actions.setSpacing(self.spacing(8))
        actions.addWidget(self.connect_button)
        actions.addWidget(self.disconnect_button)
        actions.addWidget(self.save_button)
        actions.addStretch(1)
        actions.addWidget(self.status)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(self.spacing(8), self.spacing(8), self.spacing(8), self.spacing(8))
        layout.setSpacing(self.spacing(10))
        layout.addWidget(HeadingLabel("Connection", 3, self, self.scaler))
        layout.addWidget(vci_box)
        layout.addWidget(protocol_box)
        layout.addLayout(actions)
        layout.addStretch(1)

    # -- pages ---------------------------------------------------------------
    def _build_can_page(self) -> QWidget:
        """Build the CAN and CAN FD configuration page."""
        page = QWidget(self)
        layout = QGridLayout(page)
        layout.setSpacing(self.spacing(8))
        self.bitrate_box = QComboBox(page)
        for rate in BITRATES:
            self.bitrate_box.addItem(f"{rate // 1000} kbit/s", rate)
        self.bitrate_box.setCurrentIndex(2)
        self.data_bitrate_box = QComboBox(page)
        for rate in (1_000_000, 2_000_000, 4_000_000, 5_000_000):
            self.data_bitrate_box.addItem(f"{rate // 1000} kbit/s", rate)
        self.data_bitrate_box.setCurrentIndex(1)
        self.tx_field = HexInputField(page, self.scaler, max_bytes=4, placeholder="7E0")
        self.tx_field.set_value(b"\x07\xe0")
        self.rx_field = HexInputField(page, self.scaler, max_bytes=4, placeholder="7E8")
        self.rx_field.set_value(b"\x07\xe8")
        self.functional_field = HexInputField(page, self.scaler, max_bytes=4, placeholder="7DF")
        self.functional_field.set_value(b"\x07\xdf")
        self.extended_box = QCheckBox("29-bit identifiers", page)
        self.padding_box = QCheckBox("Pad frames to 8 bytes", page)
        self.padding_box.setChecked(True)

        layout.addWidget(QLabel("Bitrate:", page), 0, 0)
        layout.addWidget(self.bitrate_box, 0, 1)
        layout.addWidget(QLabel("FD data bitrate:", page), 0, 2)
        layout.addWidget(self.data_bitrate_box, 0, 3)
        layout.addWidget(QLabel("TX identifier:", page), 1, 0)
        layout.addWidget(self.tx_field, 1, 1)
        layout.addWidget(QLabel("RX identifier:", page), 1, 2)
        layout.addWidget(self.rx_field, 1, 3)
        layout.addWidget(QLabel("Functional ID:", page), 2, 0)
        layout.addWidget(self.functional_field, 2, 1)
        layout.addWidget(self.extended_box, 2, 2)
        layout.addWidget(self.padding_box, 2, 3)
        return page

    def _build_doip_page(self) -> QWidget:
        """Build the DoIP configuration page."""
        page = QWidget(self)
        layout = QGridLayout(page)
        layout.setSpacing(self.spacing(8))
        from PySide6.QtWidgets import QLineEdit

        self.host_field = QLineEdit("192.168.0.10", page)
        self.port_box = QSpinBox(page)
        self.port_box.setRange(1, 65535)
        self.port_box.setValue(13400)
        self.source_field = HexInputField(page, self.scaler, max_bytes=2, placeholder="0E00")
        self.source_field.set_value(b"\x0e\x00")
        self.target_field = HexInputField(page, self.scaler, max_bytes=2, placeholder="1000")
        self.target_field.set_value(b"\x10\x00")
        self.tls_box = QCheckBox("Use TLS", page)
        self.activation_box = QComboBox(page)
        self.activation_box.addItem("Default (0x00)", 0x00)
        self.activation_box.addItem("WWH-OBD (0x01)", 0x01)
        self.activation_box.addItem("Central security (0xE0)", 0xE0)

        layout.addWidget(QLabel("Host:", page), 0, 0)
        layout.addWidget(self.host_field, 0, 1)
        layout.addWidget(QLabel("Port:", page), 0, 2)
        layout.addWidget(self.port_box, 0, 3)
        layout.addWidget(QLabel("Source address:", page), 1, 0)
        layout.addWidget(self.source_field, 1, 1)
        layout.addWidget(QLabel("Target address:", page), 1, 2)
        layout.addWidget(self.target_field, 1, 3)
        layout.addWidget(QLabel("Activation type:", page), 2, 0)
        layout.addWidget(self.activation_box, 2, 1)
        layout.addWidget(self.tls_box, 2, 2)
        return page

    def _build_serial_page(self) -> QWidget:
        """Build the K-Line and LIN configuration page."""
        page = QWidget(self)
        layout = QGridLayout(page)
        layout.setSpacing(self.spacing(8))
        self.port_field = QComboBox(page)
        self.port_field.setEditable(True)
        from src.utils.platform_utils import list_serial_ports

        self.port_field.addItems(list_serial_ports() or ["/dev/ttyUSB0", "COM1"])
        self.serial_baud_box = QComboBox(page)
        for rate in (9600, 10400, 19200, 38400, 57600, 115200):
            self.serial_baud_box.addItem(f"{rate} baud", rate)
        self.serial_baud_box.setCurrentIndex(1)
        self.init_box = QComboBox(page)
        self.init_box.addItems(["Fast init (ISO 14230)", "5 baud init (ISO 9141)", "None"])
        self.nad_field = HexInputField(page, self.scaler, max_bytes=1, placeholder="01")

        layout.addWidget(QLabel("Serial port:", page), 0, 0)
        layout.addWidget(self.port_field, 0, 1)
        layout.addWidget(QLabel("Baudrate:", page), 0, 2)
        layout.addWidget(self.serial_baud_box, 0, 3)
        layout.addWidget(QLabel("Initialisation:", page), 1, 0)
        layout.addWidget(self.init_box, 1, 1)
        layout.addWidget(QLabel("LIN NAD:", page), 1, 2)
        layout.addWidget(self.nad_field, 1, 3)
        return page

    def _build_j1939_page(self) -> QWidget:
        """Build the J1939 configuration page."""
        page = QWidget(self)
        layout = QGridLayout(page)
        layout.setSpacing(self.spacing(8))
        self.j1939_baud_box = QComboBox(page)
        for rate in (250_000, 500_000):
            self.j1939_baud_box.addItem(f"{rate // 1000} kbit/s", rate)
        self.j1939_source_field = HexInputField(page, self.scaler, max_bytes=1, placeholder="F9")
        self.j1939_source_field.set_value(b"\xf9")
        layout.addWidget(QLabel("Bitrate:", page), 0, 0)
        layout.addWidget(self.j1939_baud_box, 0, 1)
        layout.addWidget(QLabel("Source address:", page), 0, 2)
        layout.addWidget(self.j1939_source_field, 0, 3)
        return page

    # -- API -----------------------------------------------------------------
    def profile(self) -> ConnectionProfile:
        """Return the :class:`ConnectionProfile` described by the inputs."""
        protocol = ProtocolType(self.protocol_box.currentData())
        options: dict[str, Any] = {
            "padding_enabled": self.padding_box.isChecked(),
            "padding_byte": 0x00,
            "doip": {
                "host": self.host_field.text(),
                "port": self.port_box.value(),
                "source_address": int.from_bytes(self.source_field.value() or b"\x0e\x00", "big"),
                "target_address": int.from_bytes(self.target_field.value() or b"\x10\x00", "big"),
                "activation_type": int(self.activation_box.currentData()),
                "use_tls": self.tls_box.isChecked(),
            },
            "kline": {
                "port": self.port_field.currentText(),
                "baudrate": int(self.serial_baud_box.currentData()),
                "init_type": ["FAST_INIT", "FIVE_BAUD", "NONE"][self.init_box.currentIndex()],
            },
            "lin": {
                "port": self.port_field.currentText(),
                "baudrate": int(self.serial_baud_box.currentData()),
                "nad": int.from_bytes(self.nad_field.value() or b"\x01", "big"),
            },
            "j1939": {
                "bitrate": int(self.j1939_baud_box.currentData()),
                "source_address": int.from_bytes(self.j1939_source_field.value() or b"\xf9", "big"),
            },
        }
        return ConnectionProfile(
            name=f"{self.vci_box.currentText()} / {protocol.value}",
            vci_type=VCIType(self.vci_box.currentData()),
            channel=self.channel_box.currentText(),
            protocol=protocol,
            bitrate=int(self.bitrate_box.currentData()),
            data_bitrate=int(self.data_bitrate_box.currentData()),
            tx_id=int.from_bytes(self.tx_field.value() or b"\x07\xe0", "big"),
            rx_id=int.from_bytes(self.rx_field.value() or b"\x07\xe8", "big"),
            functional_id=int.from_bytes(self.functional_field.value() or b"\x07\xdf", "big"),
            extended_id=self.extended_box.isChecked(),
            options=options,
        )

    def apply_profile(self, profile: ConnectionProfile) -> None:
        """Load *profile* into the input widgets."""
        index = self.vci_box.findData(profile.vci_type.value)
        if index >= 0:
            self.vci_box.setCurrentIndex(index)
        index = self.protocol_box.findData(profile.protocol.value)
        if index >= 0:
            self.protocol_box.setCurrentIndex(index)
        self.tx_field.set_value(profile.tx_id.to_bytes(2, "big"))
        self.rx_field.set_value(profile.rx_id.to_bytes(2, "big"))
        self.extended_box.setChecked(profile.extended_id)
        rate_index = self.bitrate_box.findData(profile.bitrate)
        if rate_index >= 0:
            self.bitrate_box.setCurrentIndex(rate_index)

    #: Channel choices offered per VCI family.
    #:
    #: SocketCAN binds to a named kernel link, everything else indexes into a
    #: vendor device table, so the two cannot share one list.
    CHANNEL_CHOICES: dict[VCIType, tuple[str, ...]] = {
        VCIType.SOCKETCAN: ("can0", "can1", "vcan0", "vcan1", "slcan0"),
    }
    #: Channel list used when the VCI family has no specific entry.
    DEFAULT_CHANNELS: tuple[str, ...] = tuple(str(i) for i in range(8))

    def _populate_channels(self) -> None:
        """Offer the channel identifiers that match the selected VCI."""
        try:
            vci_type = VCIType(self.vci_box.currentData())
        except (TypeError, ValueError):
            vci_type = VCIType.VIRTUAL
        choices = self.CHANNEL_CHOICES.get(vci_type, self.DEFAULT_CHANNELS)
        current = self.channel_box.currentText()
        self.channel_box.blockSignals(True)
        self.channel_box.clear()
        self.channel_box.addItems(list(choices))
        if current in choices:
            self.channel_box.setCurrentText(current)
        self.channel_box.blockSignals(False)
        self.channel_box.setToolTip(
            "SocketCAN interface name, e.g. can0 (bring it up with "
            "'sudo ip link set can0 up type can bitrate 500000')"
            if vci_type is VCIType.SOCKETCAN
            else "Channel index reported by the vendor driver, starting at 1"
        )

    def _on_vci_changed(self, _index: int) -> None:
        """Refresh the channel list when the VCI family changes."""
        self._populate_channels()

    def show_devices(self, devices: list[DetectedVCI]) -> None:
        """Fill the device drop-down with the scan result."""
        self.detected = devices
        self.device_box.clear()
        for device in devices:
            self.device_box.addItem(device.label, device.vci_type.value)
        if not devices:
            self.device_box.addItem("No device detected", "")

    def set_state(self, state: ConnectionState, message: str = "") -> None:
        """Reflect the connection state in the buttons and the indicator."""
        connected = state is ConnectionState.CONNECTED
        busy = state in (ConnectionState.CONNECTING, ConnectionState.DISCONNECTING)
        self.connect_button.set_loading(busy)
        self.connect_button.setEnabled(not connected and not busy)
        self.disconnect_button.setEnabled(connected)
        profile = self.profile()
        self.status.set_state(state, profile.vci_type.display_name, profile.protocol.value,
                              profile.bitrate)
        if message and state is ConnectionState.ERROR:
            self.status.set_error(message)

    # -- events ----------------------------------------------------------------
    def _on_protocol_changed(self, _index: int) -> None:
        """Show the configuration page matching the selected protocol."""
        protocol = ProtocolType(self.protocol_box.currentData())
        page = {
            ProtocolType.CAN: 0,
            ProtocolType.CAN_FD: 0,
            ProtocolType.DOIP: 1,
            ProtocolType.ETHERNET: 1,
            ProtocolType.KLINE: 2,
            ProtocolType.LIN: 2,
            ProtocolType.J1939: 3,
            ProtocolType.FLEXRAY: 0,
        }.get(protocol, 0)
        self.stack.setCurrentIndex(page)

    def _on_connect(self) -> None:
        """Emit the connect request with the current profile."""
        self.connect_requested.emit(self.profile())


__all__ = ["ConnectionPanel", "BITRATES"]
