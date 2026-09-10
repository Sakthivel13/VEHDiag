"""Tests exercising the simulator variants."""
from __future__ import annotations

import pytest

from src.communication.protocols.can.can_protocol import CANProtocol
from src.communication.transport_layer import TransportLayer
from src.communication.vci_drivers.virtual.virtual_bus import VirtualBus
from src.diagnostics.uds_client import UDSClient, UDSClientConfig
from tests.simulation.mock_ecu import (
    load_simulator_config,
    make_empty_simulator,
    make_flaky_simulator,
    make_pending_simulator,
    make_simulator,
    make_slow_simulator,
)
from tests.simulation.mock_vci import MockVCIDriver


def build_client(
    simulator, bus: VirtualBus, timing_ms: float = 500.0
) -> tuple[UDSClient, MockVCIDriver, TransportLayer]:
    """Return a client, the recording driver and the transport."""
    driver = MockVCIDriver(virtual_bus=bus, simulator=simulator)
    driver.connect()
    transport = TransportLayer(CANProtocol(driver))
    transport.connect()
    return UDSClient(transport, UDSClientConfig(p2_client_ms=timing_ms)), driver, transport


def close(driver: MockVCIDriver, transport: TransportLayer) -> None:
    """Shut the transport and the driver down in the right order."""
    transport.disconnect()
    driver.disconnect()


class TestConfiguration:
    """The YAML configuration."""

    def test_configuration_is_complete(self) -> None:
        """Every section the simulator needs is present."""
        config = load_simulator_config()
        assert config["rx_id"] == 0x7E0
        assert "F190" in config["dids"]
        assert len(config["dtcs"]) == 3
        assert "0x01" in config["security_levels"]

    def test_simulator_uses_the_configuration(self) -> None:
        """Values from the YAML end up in the simulator."""
        simulator = make_simulator()
        assert simulator.rx_id == 0x7E0
        assert len(simulator.dtcs) == 3
        assert 0xF190 in simulator.dids


class TestVariants:
    """The preconfigured simulator variants."""

    def test_default(self) -> None:
        """The default simulator answers the standard services."""
        bus = VirtualBus("default")
        client, driver, transport = build_client(make_simulator(bus), bus)
        assert client.change_session(0x03).is_positive()
        assert client.read_data_by_identifier(0xF190).is_positive()
        assert driver.sent_hex
        close(driver, transport)

    def test_pending_responses(self) -> None:
        """Pending responses are consumed transparently."""
        bus = VirtualBus("pending")
        client, driver, transport = build_client(make_pending_simulator(bus, 3), bus, 2000.0)
        response = client.change_session(0x03)
        assert response.is_positive()
        assert response.pending_count == 3
        close(driver, transport)

    def test_slow_ecu_times_out(self) -> None:
        """A slow ECU produces a timeout with a short P2."""
        bus = VirtualBus("slow")
        client, driver, transport = build_client(make_slow_simulator(bus, 400), bus, timing_ms=50.0)
        assert client.change_session(0x03).timed_out
        close(driver, transport)

    def test_empty_fault_memory(self) -> None:
        """A simulator without DTCs reports an empty list."""
        from src.diagnostics.services.dtc_services.read_dtc_information import ReadDTCInformation

        bus = VirtualBus("empty")
        client, driver, transport = build_client(make_empty_simulator(bus), bus)
        assert len(ReadDTCInformation(client).read_by_status_mask()) == 0
        close(driver, transport)

    def test_flaky_ecu_is_retried(self) -> None:
        """Injected busy responses are retried automatically."""
        bus = VirtualBus("flaky")
        driver = MockVCIDriver(virtual_bus=bus, simulator=make_flaky_simulator(bus, 0.5))
        driver.connect()
        transport = TransportLayer(CANProtocol(driver))
        transport.connect()
        client = UDSClient(
            transport, UDSClientConfig(retry_on_busy=True, max_retries=8, retry_delay_ms=5)
        )
        results = [client.change_session(0x03).is_positive() for _ in range(10)]
        assert any(results)
        close(driver, transport)


class TestRecording:
    """The recording mock driver."""

    def test_frames_are_recorded(self) -> None:
        """Every transmitted and received frame is captured."""
        bus = VirtualBus("record")
        client, driver, transport = build_client(make_simulator(bus), bus)
        client.change_session(0x03)
        assert driver.sent_hex[0].startswith("02 10 03")
        assert any(frame.startswith("06 50 03") for frame in driver.received_hex)
        close(driver, transport)

    def test_multi_frame_is_segmented(self) -> None:
        """A long response arrives as several CAN frames."""
        bus = VirtualBus("segmented")
        client, driver, transport = build_client(make_simulator(bus), bus)
        driver.clear_recordings()
        client.read_data_by_identifier(0xF190)
        assert len(driver.received) >= 3  # first frame plus consecutive frames
        close(driver, transport)


class TestSimulatorResilience:
    """The simulator must survive misbehaving testers."""

    def test_survives_a_tester_vanishing_mid_transfer(self) -> None:
        """An abrupt disconnect during a multi-frame reply must not kill it.

        The tester requests the VIN, which needs a multi-frame ISO-TP answer,
        and then disappears before sending the flow control frame. The
        simulator hits an ``N_Bs`` timeout while sending; it has to abandon
        that exchange and keep serving the next tester.
        """
        import threading
        import time

        from src.diagnostics.uds_client import UDSClientConfig

        bus = VirtualBus("resilience")
        simulator = make_simulator(bus)
        simulator.start()
        try:
            assert simulator._thread is not None and simulator._thread.is_alive()

            first = MockVCIDriver(virtual_bus=bus, simulator=None, start_simulator=False)
            first.connect()
            first_transport = TransportLayer(CANProtocol(first))
            first_transport.connect()
            client = UDSClient(first_transport, UDSClientConfig(p2_client_ms=30.0))

            def request() -> None:
                """Ask for the VIN and swallow the inevitable timeout."""
                try:
                    client.read_data_by_identifier(0xF190)
                except Exception:  # noqa: BLE001 - the tester is being killed
                    pass

            worker = threading.Thread(target=request)
            worker.start()
            time.sleep(0.005)
            first_transport.disconnect()
            first.disconnect()
            worker.join(timeout=5)
            time.sleep(1.6)  # outlast the 1000 ms N_Bs timeout

            assert simulator._thread is not None
            assert simulator._thread.is_alive(), "the simulator thread died"

            second = MockVCIDriver(virtual_bus=bus, simulator=None, start_simulator=False)
            second.connect()
            second_transport = TransportLayer(CANProtocol(second))
            second_transport.connect()
            recovered = UDSClient(second_transport, UDSClientConfig(p2_client_ms=1000.0))
            response = recovered.read_data_by_identifier(0xF190)
            assert not response.timed_out
            assert bytes(response.data[2:]) == b"WBAZZZ0GM12345678"
            second_transport.disconnect()
            second.disconnect()
        finally:
            simulator.stop()
