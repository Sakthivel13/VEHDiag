"""Unit tests for the UDS client."""
from __future__ import annotations

import pytest

from src.core.enums.nrc_enums import NegativeResponseCode
from src.core.exceptions import NegativeResponseError, NotConnectedError, RequestValidationError
from src.diagnostics.uds_client import UDSClient, UDSClientConfig


class TestPositiveResponses:
    """Positive response handling."""

    def test_session_change(self, client: UDSClient) -> None:
        """The session change is accepted and the state is updated."""
        response = client.change_session(0x03)
        assert response.is_positive()
        assert response.raw[0] == 0x50
        assert client.state.active_session == 0x03

    def test_timing_is_extracted(self, client: UDSClient) -> None:
        """P2 and P2* are taken from the response."""
        client.change_session(0x03)
        assert client.state.timing.p2_server_ms == 50.0
        assert client.state.timing.p2_star_server_ms == 5000.0

    def test_read_did(self, client: UDSClient) -> None:
        """A known DID returns its payload."""
        response = client.read_data_by_identifier(0xF190)
        assert response.is_positive()
        assert response.raw[1:3] == b"\xf1\x90"
        assert len(response.raw[3:]) == 17

    def test_read_multiple_dids(self, client: UDSClient) -> None:
        """Several identifiers can be read in one request."""
        response = client.read_data_by_identifier(0xF190, 0xF18C)
        assert response.is_positive()
        assert b"\xf1\x90" in response.raw
        assert b"\xf1\x8c" in response.raw

    def test_response_metadata(self, client: UDSClient) -> None:
        """The response records the elapsed time and the request."""
        response = client.change_session(0x03)
        assert response.elapsed_ms > 0
        assert response.request == b"\x10\x03"
        assert "positive response" in response.summary()


class TestNegativeResponses:
    """Negative response handling."""

    def test_unknown_did_is_out_of_range(self, client: UDSClient) -> None:
        """An unsupported DID yields NRC 0x31."""
        response = client.read_data_by_identifier(0xFFFF)
        assert response.is_negative
        assert response.nrc == int(NegativeResponseCode.REQUEST_OUT_OF_RANGE)
        assert not response.is_positive()

    def test_nrc_description(self, client: UDSClient) -> None:
        """The NRC text explains the failure."""
        response = client.read_data_by_identifier(0xFFFF)
        assert "requestOutOfRange" in response.nrc_text

    def test_unsupported_service(self, client: UDSClient) -> None:
        """An unimplemented service yields NRC 0x11."""
        response = client.send_request(bytes([0x24, 0xF1, 0x90]))
        assert response.is_negative
        assert response.nrc == int(NegativeResponseCode.SERVICE_NOT_SUPPORTED)

    def test_raise_on_negative(self, transport) -> None:
        """The client can raise instead of returning a negative response."""
        strict = UDSClient(transport, UDSClientConfig(raise_on_negative=True))
        with pytest.raises(NegativeResponseError) as info:
            strict.read_data_by_identifier(0xFFFF)
        assert info.value.nrc == 0x31
        assert info.value.recovery_hint

    def test_statistics_count_negatives(self, client: UDSClient) -> None:
        """Negative responses are counted separately."""
        client.read_data_by_identifier(0xFFFF)
        assert client.statistics.negative == 1
        assert client.statistics.positive == 0


class TestSuppression:
    """Suppress positive response bit."""

    def test_tester_present_is_suppressed(self, client: UDSClient) -> None:
        """A suppressed request reports success without a response."""
        response = client.tester_present(suppress=True)
        assert response.suppressed
        assert response.is_positive()
        assert response.raw == b""

    def test_tester_present_without_suppression(self, client: UDSClient) -> None:
        """Without the bit the ECU answers normally."""
        response = client.tester_present(suppress=False)
        assert response.raw[:2] == b"\x7e\x00"


class TestValidation:
    """Request validation."""

    def test_empty_request_rejected(self, client: UDSClient) -> None:
        """An empty payload is refused."""
        with pytest.raises(ValueError):
            client.send_request(b"")

    def test_reserved_sid_rejected(self, client: UDSClient) -> None:
        """0x7F may not be used as a request SID."""
        with pytest.raises(ValueError):
            client.send_request(b"\x7f\x22")

    def test_read_did_requires_identifier(self, client: UDSClient) -> None:
        """At least one DID must be supplied."""
        with pytest.raises(RequestValidationError):
            client.read_data_by_identifier()

    def test_disconnected_client(self, transport) -> None:
        """Sending on a closed transport raises."""
        disconnected = UDSClient(transport)
        transport.disconnect()
        with pytest.raises(NotConnectedError):
            disconnected.change_session(0x03)


class TestSecurityAccess:
    """Security access through the client helpers."""

    def test_seed_then_key(self, client: UDSClient) -> None:
        """The demo algorithm unlocks the simulated ECU."""
        client.change_session(0x03)
        seed_response = client.security_access(0x01)
        assert seed_response.is_positive()
        seed = seed_response.raw[2:]
        key = bytes((~b ^ 0xFF) & 0xFF for b in seed)
        assert client.security_access(0x02, key).is_positive()
        assert client.state.unlocked_level == 0x02

    def test_wrong_key_is_rejected(self, client: UDSClient) -> None:
        """An invalid key produces NRC 0x35."""
        client.change_session(0x03)
        client.security_access(0x01)
        response = client.security_access(0x02, b"\x00\x00\x00\x00")
        assert response.is_negative
        assert response.nrc == int(NegativeResponseCode.INVALID_KEY)


class TestListeners:
    """Response listeners."""

    def test_listener_receives_every_response(self, client: UDSClient) -> None:
        """Registered listeners see all exchanges."""
        seen: list[object] = []
        client.add_listener(seen.append)
        client.change_session(0x03)
        client.read_data_by_identifier(0xF190)
        assert len(seen) == 2
        client.remove_listener(seen.append)

    def test_broken_listener_does_not_break_the_client(self, client: UDSClient) -> None:
        """An exception in a listener is swallowed."""

        def broken(_response: object) -> None:
            raise RuntimeError("boom")

        client.add_listener(broken)
        assert client.change_session(0x03).is_positive()
