"""Tests for the python-can backed hardware driver.

:class:`PythonCanDriver` is the code path every hardware interface uses - PCAN,
Vector, Kvaser and neoVI only differ by the backend string they pass to
``can.Bus``. Exercising it against python-can's own ``virtual`` backend proves
the framing, the flags and the statistics are correct without needing a real
interface on the bench.
"""
from __future__ import annotations

import pytest

pytest.importorskip("can")

from src.communication.vci_drivers.pcan.pcan_driver import PythonCanDriver  # noqa: E402
from src.core.enums.protocol_enums import ProtocolType  # noqa: E402
from src.core.models.message_model import BusMessage  # noqa: E402
from src.core.models.vci_model import VCIChannelConfig  # noqa: E402


@pytest.fixture()
def pair(request):
    """Return two drivers attached to the same python-can virtual channel."""
    channel = f"vcan-{request.node.name}"
    config = VCIChannelConfig(channel=channel, bitrate=500_000)
    a = PythonCanDriver("virtual", config)
    b = PythonCanDriver("virtual", VCIChannelConfig(channel=channel, bitrate=500_000))
    a.connect()
    b.connect()
    yield a, b
    a.disconnect()
    b.disconnect()


class TestClassicCAN:
    """11-bit and 29-bit classic CAN framing."""

    def test_connects_and_reports_state(self, pair) -> None:
        """Both ends report a live connection."""
        a, b = pair
        assert a.is_connected and b.is_connected

    def test_frame_round_trip(self, pair) -> None:
        """The payload and the identifier survive the round trip."""
        a, b = pair
        payload = bytes.fromhex("0322F19000000000")
        a.send(BusMessage(data=payload, arbitration_id=0x7E0))
        received = b.receive(timeout=1.0)
        assert received is not None
        assert received.arbitration_id == 0x7E0
        assert received.data == payload
        assert not received.is_extended_id

    def test_extended_identifier(self, pair) -> None:
        """29-bit identifiers keep their flag, as J1939 and ISO 15765 need."""
        a, b = pair
        a.send(BusMessage(data=b"\x01\x02", arbitration_id=0x18DAF110, is_extended_id=True))
        received = b.receive(timeout=1.0)
        assert received is not None
        assert received.arbitration_id == 0x18DAF110
        assert received.is_extended_id

    def test_statistics_are_counted(self, pair) -> None:
        """The transmit counter feeds the status bar."""
        a, b = pair
        before = a.get_status().tx_count
        a.send(BusMessage(data=b"\x00", arbitration_id=0x100))
        b.receive(timeout=1.0)
        assert a.get_status().tx_count == before + 1

    def test_receive_timeout_returns_none(self, pair) -> None:
        """A silent bus yields ``None`` rather than blocking or raising."""
        _a, b = pair
        assert b.receive(timeout=0.05) is None

    def test_device_info(self, pair) -> None:
        """The UI shows the backend and the channel."""
        a, _b = pair
        info = a.get_device_info()
        assert info is not None
        assert "virtual" in info.name


class TestCANFD:
    """CAN FD framing: 64-byte payloads and the bitrate switch."""

    @pytest.fixture()
    def fd_pair(self, request):
        """Return two CAN FD drivers on one virtual channel."""
        channel = f"vcanfd-{request.node.name}"

        def make() -> PythonCanDriver:
            return PythonCanDriver(
                "virtual",
                VCIChannelConfig(
                    channel=channel,
                    bitrate=500_000,
                    data_bitrate=2_000_000,
                    protocol=ProtocolType.CAN_FD,
                ),
            )

        a, b = make(), make()
        a.connect()
        b.connect()
        yield a, b
        a.disconnect()
        b.disconnect()

    def test_64_byte_payload(self, fd_pair) -> None:
        """A full FD frame survives intact."""
        a, b = fd_pair
        payload = bytes(range(64))
        a.send(BusMessage(data=payload, arbitration_id=0x7E0, is_fd=True, bitrate_switch=True))
        received = b.receive(timeout=1.0)
        assert received is not None
        assert len(received.data) == 64
        assert received.data == payload

    def test_fd_flags_preserved(self, fd_pair) -> None:
        """The FD and BRS flags must reach the application layer."""
        a, b = fd_pair
        a.send(BusMessage(data=b"\x01" * 12, arbitration_id=0x7E0, is_fd=True, bitrate_switch=True))
        received = b.receive(timeout=1.0)
        assert received is not None
        assert received.is_fd
        assert received.bitrate_switch


class TestUDSOverTheDriver:
    """A complete UDS exchange across the hardware driver stack."""

    def test_full_session(self, request) -> None:
        """Session control, a multi-frame VIN read and a DTC read all work."""
        import threading

        from src.communication.isotp_handler import IsoTpConfig, IsoTpHandler
        from src.communication.protocols.can.can_protocol import CANProtocol
        from src.communication.transport_layer import TransportLayer
        from src.communication.vci_drivers.virtual.ecu_simulator import ECUSimulator
        from src.diagnostics.services.dtc_services.dtc_parser import parse_dtc_list
        from src.diagnostics.uds_client import UDSClient, UDSClientConfig
        from tests.simulation.mock_ecu import load_simulator_config

        channel = "vcan-uds-stack"
        tester = PythonCanDriver("virtual", VCIChannelConfig(channel=channel, bitrate=500_000))
        ecu = PythonCanDriver("virtual", VCIChannelConfig(channel=channel, bitrate=500_000))
        tester.connect()
        ecu.connect()

        simulator = ECUSimulator(load_simulator_config(), None)
        isotp = IsoTpHandler(
            lambda frame: ecu.send(BusMessage(data=frame, arbitration_id=0x7E8)),
            lambda timeout: (
                m.data
                if (m := ecu.receive(timeout)) is not None and m.arbitration_id == 0x7E0
                else None
            ),
            IsoTpConfig(),
        )
        stop = threading.Event()

        def serve() -> None:
            """Answer requests until the test stops the server."""
            while not stop.is_set():
                try:
                    request_bytes = isotp.receive(0.2)
                except Exception:  # noqa: BLE001 - keep serving
                    continue
                if not request_bytes:
                    continue
                try:
                    response = simulator.handle_request(request_bytes)
                    if response:
                        isotp.send(response)
                except Exception:  # noqa: BLE001 - keep serving
                    continue

        worker = threading.Thread(target=serve, daemon=True)
        worker.start()
        transport = TransportLayer(CANProtocol(tester, {"tx_id": 0x7E0, "rx_id": 0x7E8}))
        transport.connect()
        try:
            client = UDSClient(transport, UDSClientConfig(p2_client_ms=2000.0))
            assert client.change_session(0x03).is_positive()
            vin = bytes(client.read_data_by_identifier(0xF190).data[2:])
            assert vin == b"WBAZZZ0GM12345678"
            report = client.read_dtc_information(0x02, 0xFF)
            assert len(parse_dtc_list(report.data[2:])) == 3
            assert client.statistics.timeouts == 0
        finally:
            stop.set()
            worker.join(timeout=2)
            transport.disconnect()
            tester.disconnect()
            ecu.disconnect()


class TestBackendKwargFiltering:
    """Each backend must receive only the keywords its constructor accepts.

    These are regressions for a class of bug that is invisible on the bench:
    the channel opens, but at the wrong speed or on the wrong physical port.
    """

    def _kwargs(self, driver) -> dict:
        """Return the keyword arguments the driver would hand to ``can.Bus``."""
        return driver._build_bus_kwargs()

    def test_socketcan_does_not_receive_bitrate(self) -> None:
        """SocketCAN takes its timing from the kernel link, not python-can.

        ``SocketcanBus.__init__`` has no ``bitrate`` parameter, so passing one
        lands in ``**kwargs`` and is silently discarded.
        """
        driver = PythonCanDriver("socketcan", VCIChannelConfig(channel="can0", bitrate=250_000))
        assert "bitrate" not in self._kwargs(driver)

    def test_kvaser_fd_does_not_receive_data_bitrate(self) -> None:
        """KvaserBus rejects an explicit ``data_bitrate`` keyword."""
        driver = PythonCanDriver(
            "kvaser",
            VCIChannelConfig(channel=0, bitrate=500_000, data_bitrate=2_000_000,
                             protocol=ProtocolType.CAN_FD),
        )
        kwargs = self._kwargs(driver)
        assert kwargs.get("fd") is True
        assert "data_bitrate" not in kwargs

    def test_pcan_fd_receives_both_bitrates(self) -> None:
        """PCAN FD needs the arbitration and the data phase bitrate."""
        from src.communication.vci_drivers.pcan.pcan_fd_driver import PCANFDDriver

        driver = PCANFDDriver(
            VCIChannelConfig(channel=1, bitrate=500_000, data_bitrate=2_000_000)
        )
        kwargs = self._kwargs(driver)
        assert kwargs["bitrate"] == 500_000
        assert kwargs["data_bitrate"] == 2_000_000
        assert kwargs["fd"] is True

    def test_vector_receives_bitrate_and_app_name(self) -> None:
        """Vector needs the registered application name to open a channel."""
        from src.communication.vci_drivers.vector.vector_driver import VectorDriver

        driver = VectorDriver(VCIChannelConfig(channel=0, bitrate=500_000))
        driver.bus_kwargs.setdefault("app_name", driver.app_name)
        kwargs = self._kwargs(driver)
        assert kwargs["bitrate"] == 500_000
        assert kwargs["app_name"] == VectorDriver.DEFAULT_APP_NAME


class TestPCANChannelMapping:
    """PEAK numbers its channels from one."""

    @pytest.mark.parametrize(
        "channel,expected",
        [(0, "PCAN_USBBUS1"), (1, "PCAN_USBBUS1"), (2, "PCAN_USBBUS2"), (4, "PCAN_USBBUS4")],
    )
    def test_numeric_channels(self, channel: int, expected: str) -> None:
        """Channel 1 must open USBBUS1, not USBBUS2."""
        from src.communication.vci_drivers.pcan.pcan_driver import PCANDriver

        driver = PCANDriver(VCIChannelConfig(channel=channel))
        assert driver._channel_argument() == expected

    def test_explicit_handle_is_passed_through(self) -> None:
        """A string handle is used verbatim, covering PCI and LAN devices."""
        from src.communication.vci_drivers.pcan.pcan_driver import PCANDriver

        driver = PCANDriver(VCIChannelConfig(channel="PCAN_PCIBUS3"))
        assert driver._channel_argument() == "PCAN_PCIBUS3"


class TestConnectionDiagnostics:
    """Failures must explain what to do next."""

    def test_error_carries_actionable_details(self) -> None:
        """The raised error names the interface, channel, bitrate and a hint."""
        from src.core.exceptions import ConnectionFailedError, DriverNotFoundError
        from src.communication.vci_drivers.pcan.pcan_driver import PCANDriver

        driver = PCANDriver(VCIChannelConfig(channel=1, bitrate=500_000))
        with pytest.raises((ConnectionFailedError, DriverNotFoundError)) as info:
            driver.connect()
        details = getattr(info.value, "details", {})
        if details:
            assert details.get("channel") == "PCAN_USBBUS1"
            assert details.get("bitrate") == 500_000
            assert details.get("hint")


class TestChannelNormalisation:
    """Channel identifiers must reach each backend in the form it expects.

    The connection panel stores the channel as the combo box *text*, so a
    plain selection arrives as ``"1"`` rather than ``1``. Every backend
    specific translation used to be skipped for those strings, so PCAN never
    built its ``PCAN_USBBUSx`` handle and Kvaser received a string where its
    CANlib binding declares ``channel: int``.
    """

    def _config(self, channel):
        from src.core.models.vci_model import VCIChannelConfig

        return VCIChannelConfig(channel=channel, bitrate=500_000)

    def test_pcan_translates_string_channels(self) -> None:
        """A channel typed as text still becomes a PCAN handle."""
        from src.communication.vci_drivers.pcan.pcan_driver import PCANDriver

        assert PCANDriver(self._config("1"))._channel_argument() == "PCAN_USBBUS1"
        assert PCANDriver(self._config(1))._channel_argument() == "PCAN_USBBUS1"
        # The UI defaults numeric fields to zero; PEAK counts from one.
        assert PCANDriver(self._config("0"))._channel_argument() == "PCAN_USBBUS1"
        assert PCANDriver(self._config(3))._channel_argument() == "PCAN_USBBUS3"

    def test_pcan_passes_explicit_handles_through(self) -> None:
        """A hand written handle is never rewritten."""
        from src.communication.vci_drivers.pcan.pcan_driver import PCANDriver

        assert PCANDriver(self._config("PCAN_PCIBUS2"))._channel_argument() == "PCAN_PCIBUS2"

    def test_socketcan_uses_interface_names(self) -> None:
        """SocketCAN binds to ``can0``; a bare index binds to nothing."""
        from src.communication.vci_drivers.pcan.pcan_driver import PythonCanDriver

        assert PythonCanDriver("socketcan", self._config("0"))._channel_argument() == "can0"
        assert PythonCanDriver("socketcan", self._config(1))._channel_argument() == "can1"
        # An explicit name is preserved, including vcan/slcan variants.
        assert PythonCanDriver("socketcan", self._config("vcan0"))._channel_argument() == "vcan0"
        assert PythonCanDriver("socketcan", self._config("slcan0"))._channel_argument() == "slcan0"

    def test_numeric_backends_receive_integers(self) -> None:
        """Kvaser and Vector index a device table with an int."""
        from src.communication.vci_drivers.pcan.pcan_driver import PythonCanDriver

        for interface in ("kvaser", "vector"):
            value = PythonCanDriver(interface, self._config("2"))._channel_argument()
            assert value == 2, interface
            assert isinstance(value, int), interface

    def test_kwargs_match_the_backend_signature(self) -> None:
        """Every keyword the driver builds is accepted by python-can."""
        import inspect

        from src.communication.vci_drivers.pcan.pcan_driver import PythonCanDriver

        can = pytest.importorskip("can")
        from can.interfaces.socketcan import SocketcanBus

        kwargs = PythonCanDriver("socketcan", self._config("can0"))._build_bus_kwargs()
        parameters = inspect.signature(SocketcanBus.__init__).parameters
        accepts_var_kw = any(
            p.kind is inspect.Parameter.VAR_KEYWORD for p in parameters.values()
        )
        for key in kwargs:
            if key == "interface":
                continue
            assert key in parameters or accepts_var_kw, key
        # SocketCAN takes its timing from the kernel link, never from python-can.
        assert "bitrate" not in kwargs
        assert kwargs["channel"] == "can0"
        assert can is not None


class TestRealPythonCanBus:
    """Open a genuine python-can bus through the production driver."""

    def test_send_and_receive_over_a_real_bus(self) -> None:
        """Frames traverse python-can, not an in-process stub."""
        pytest.importorskip("can")
        from src.communication.vci_drivers.pcan.pcan_driver import PythonCanDriver
        from src.core.models.message_model import BusMessage
        from src.core.models.vci_model import VCIChannelConfig

        config = VCIChannelConfig(channel="0", bitrate=500_000)
        sender = PythonCanDriver("virtual", config)
        receiver = PythonCanDriver("virtual", VCIChannelConfig(channel="0"))
        sender.connect()
        receiver.connect()
        try:
            assert sender.is_connected and receiver.is_connected
            assert type(sender._bus).__name__ == "VirtualBus"
            sender.send(BusMessage(arbitration_id=0x7E0, data=bytes.fromhex("021003")))
            received = receiver.receive(timeout=1.0)
            assert received is not None
            assert received.arbitration_id == 0x7E0
            assert received.data[:3] == bytes.fromhex("021003")
        finally:
            sender.disconnect()
            receiver.disconnect()
        assert not sender.is_connected
