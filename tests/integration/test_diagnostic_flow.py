"""Integration tests covering complete diagnostic flows."""
from __future__ import annotations

import pytest

from src.communication.connection_manager import ConnectionManager, ConnectionProfile
from src.core.enums.protocol_enums import ConnectionState, ProtocolType
from src.core.enums.vci_enums import VCIType
from src.diagnostics.service_dispatcher import ServiceDispatcher
from src.diagnostics.services.dtc_services.clear_dtc import ClearDiagnosticInformation
from src.diagnostics.services.dtc_services.read_dtc_information import ReadDTCInformation
from src.diagnostics.services.ecu_reset.ecu_reset_service import ECUReset
from src.diagnostics.services.security.security_access import SecurityAccess
from src.diagnostics.services.session_control.diagnostic_session_control import (
    DiagnosticSessionControl,
)
from src.diagnostics.services.transfer_services.transfer_manager import TransferManager
from src.diagnostics.uds_client import UDSClient

pytestmark = pytest.mark.integration


class TestConnectionLifecycle:
    """The whole connection stack."""

    def test_connect_and_disconnect(self, config, event_bus) -> None:
        """The manager brings up and tears down every layer."""
        manager = ConnectionManager(config, event_bus)
        transport = manager.connect(ConnectionProfile())
        assert manager.state is ConnectionState.CONNECTED
        assert transport.is_connected
        manager.disconnect()
        assert manager.state is ConnectionState.DISCONNECTED

    def test_reconnect(self, config, event_bus) -> None:
        """Reconnecting reuses the profile."""
        manager = ConnectionManager(config, event_bus)
        manager.connect(ConnectionProfile())
        assert manager.reconnect()
        assert manager.is_connected
        manager.disconnect()

    def test_connection_events(self, config, event_bus) -> None:
        """Connecting publishes the expected events."""
        from src.core.event_bus import EventType

        seen: list[str] = []
        event_bus.subscribe(EventType.COMM_CONNECTED, lambda e: seen.append("connected"))
        event_bus.subscribe(EventType.COMM_DISCONNECTED, lambda e: seen.append("disconnected"))
        manager = ConnectionManager(config, event_bus)
        manager.connect(ConnectionProfile())
        manager.disconnect()
        assert "connected" in seen and "disconnected" in seen

    def test_info_reports_the_stack(self, connection: ConnectionManager) -> None:
        """The info mapping describes every layer."""
        info = connection.get_info()
        assert info["state"] == "CONNECTED"
        assert info["transport"]["protocol"] == "CAN"
        assert info["device"]["name"]


class TestFullDiagnosticSession:
    """A realistic diagnostic session from start to finish."""

    def test_identification_flow(self, connection: ConnectionManager, config) -> None:
        """Session change followed by reading the identification block."""
        from src.diagnostics.services.data_services.read_data_by_id import (
            ReadDataByIdentifier,
            build_registry,
        )

        client = UDSClient(connection.transport)
        assert DiagnosticSessionControl(client).enter_extended().accepted
        service = ReadDataByIdentifier(client, build_registry(config.did_definitions()))
        identification = service.read_identification()
        assert identification["VIN"].startswith("WBA")
        assert "ECU Serial Number" in identification

    def test_dtc_flow(self, connection: ConnectionManager) -> None:
        """Read, inspect and clear the fault memory."""
        client = UDSClient(connection.transport)
        DiagnosticSessionControl(client).enter_extended()
        reader = ReadDTCInformation(client)
        before = reader.read_by_status_mask()
        assert len(before) == 3
        snapshot = reader.read_snapshot(before.dtcs[0].code)
        assert snapshot.snapshots
        result = ClearDiagnosticInformation(client).clear_all()
        assert result.accepted and result.cleared_count == 3
        assert len(reader.read_by_status_mask()) == 0

    def test_security_flow(self, connection: ConnectionManager) -> None:
        """Unlock the ECU and confirm the state is tracked."""
        client = UDSClient(connection.transport)
        DiagnosticSessionControl(client).enter_extended()
        result = SecurityAccess(client, "xor_complement").execute(0x01)
        assert result.unlocked
        assert client.state.unlocked_level == 0x02

    def test_complete_flash_sequence(self, connection: ConnectionManager) -> None:
        """The standard programming sequence transfers a firmware image."""
        client = UDSClient(connection.transport)
        session = DiagnosticSessionControl(client)
        assert session.enter_extended().accepted
        client.control_dtc_setting(False)
        client.communication_control(0x03, 0x01)
        assert session.enter_programming().accepted
        assert SecurityAccess(client, "add_constant").execute(0x11).unlocked

        payload = bytes(i & 0xFF for i in range(4096))
        report = TransferManager(client).download(0x08000000, payload)
        assert report.successful
        assert report.bytes_transferred == len(payload)

        reset = ECUReset(client).execute(0x01, wait_s=0.0, verify=False)
        assert reset.accepted

    def test_dispatcher_routes_every_service(self, connection: ConnectionManager) -> None:
        """The dispatcher can execute the common services."""
        client = UDSClient(connection.transport)
        dispatcher = ServiceDispatcher(client)
        assert dispatcher.execute(0x10, 0x03).accepted
        assert dispatcher.execute(0x22, 0xF190)
        assert len(dispatcher.execute(0x19, 0x02)) == 3
        assert len(dispatcher.history) == 3
        assert all(record.succeeded for record in dispatcher.history)


class TestErrorHandling:
    """Failure paths."""

    def test_service_in_wrong_session(self, connection: ConnectionManager) -> None:
        """Security access is refused in the default session."""
        client = UDSClient(connection.transport)
        response = client.security_access(0x01)
        assert response.is_negative

    def test_error_injection(self, config, event_bus) -> None:
        """Injected transmission errors surface as timeouts."""
        manager = ConnectionManager(config, event_bus)
        transport = manager.connect(ConnectionProfile())
        driver = manager.driver
        driver.inject_errors(drop=1.0)
        client = UDSClient(transport)
        response = client.change_session(0x03)
        assert response.timed_out
        driver.inject_errors()
        manager.disconnect()

    def test_pending_response_is_resolved(self, config, event_bus) -> None:
        """A ``0x78`` pending response is consumed transparently."""
        from src.communication.protocols.can.can_protocol import CANProtocol
        from src.communication.transport_layer import TransportLayer
        from src.communication.vci_drivers.virtual.ecu_simulator import ECUSimulator
        from src.communication.vci_drivers.virtual.virtual_bus import VirtualBus
        from src.communication.vci_drivers.virtual.virtual_vci_driver import VirtualVCIDriver

        bus = VirtualBus("pending")
        simulator = ECUSimulator(
            {"support_pending_response": True, "pending_response_count": 2}, bus
        )
        driver = VirtualVCIDriver(virtual_bus=bus, simulator=simulator, event_bus=event_bus)
        driver.connect()
        transport = TransportLayer(CANProtocol(driver, event_bus=event_bus), event_bus=event_bus)
        transport.connect()
        client = UDSClient(transport)
        response = client.change_session(0x03)
        assert response.is_positive()
        assert response.pending_count == 2
        transport.disconnect()
        driver.disconnect()
