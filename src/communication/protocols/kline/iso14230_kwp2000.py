"""ISO 14230-4 (KWP2000) handler and service mapping."""
from __future__ import annotations

from typing import Any, Final

from ....core.enums.protocol_enums import KLineInitType
from ....core.event_bus import EventBus
from ....core.interfaces.i_vci_driver import IVCIDriver
from .kline_protocol import KLineProtocol
from .kline_timing import KLineTiming

#: KWP2000 service identifiers mapped to their UDS equivalent.
KWP_TO_UDS: Final[dict[int, int]] = {
    0x10: 0x10,  # startDiagnosticSession -> DiagnosticSessionControl
    0x11: 0x11,  # ecuReset
    0x14: 0x14,  # clearDiagnosticInformation
    0x18: 0x19,  # readDTCByStatus -> ReadDTCInformation
    0x1A: 0x22,  # readEcuIdentification -> ReadDataByIdentifier
    0x21: 0x22,  # readDataByLocalIdentifier -> ReadDataByIdentifier
    0x22: 0x22,  # readDataByCommonIdentifier
    0x23: 0x23,  # readMemoryByAddress
    0x27: 0x27,  # securityAccess
    0x28: 0x28,  # communicationControl
    0x2E: 0x2E,  # writeDataByCommonIdentifier
    0x30: 0x2F,  # inputOutputControlByLocalIdentifier
    0x31: 0x31,  # startRoutineByLocalIdentifier -> RoutineControl
    0x34: 0x34,  # requestDownload
    0x35: 0x35,  # requestUpload
    0x36: 0x36,  # transferData
    0x37: 0x37,  # requestTransferExit
    0x3E: 0x3E,  # testerPresent
    0x81: 0x10,  # startCommunication
    0x82: 0x10,  # stopCommunication
    0x83: 0x83,  # accessTimingParameter
}

#: Header format variants defined by ISO 14230-2.
HEADER_FORMATS: Final[dict[str, str]] = {
    "no_address": "format byte only (length in the format byte)",
    "with_address": "format + target + source",
    "with_length": "format + length byte",
    "full": "format + target + source + length",
}


class KWP2000Handler(KLineProtocol):
    """K-Line handler using ISO 14230 framing and fast initialisation."""

    def __init__(
        self,
        driver: IVCIDriver | None = None,
        config: dict[str, Any] | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        """Force fast initialisation and KWP2000 framing."""
        merged = dict(config or {})
        merged["init_type"] = KLineInitType.FAST_INIT.value
        super().__init__(driver, merged, event_bus)
        self.use_kwp_framing = True
        self.timing = KLineTiming.kwp2000_fast()

    def start_communication(self) -> bytes | None:
        """Send the ``StartCommunication`` (0x81) request."""
        return self.request(bytes([0x81]))

    def stop_communication(self) -> bytes | None:
        """Send the ``StopCommunication`` (0x82) request."""
        return self.request(bytes([0x82]))

    @staticmethod
    def to_uds(kwp_service: int) -> int:
        """Return the UDS service identifier equivalent to *kwp_service*."""
        return KWP_TO_UDS.get(kwp_service, kwp_service)

    @staticmethod
    def from_uds(uds_service: int) -> int:
        """Return the KWP2000 service identifier for *uds_service*."""
        for kwp, uds in KWP_TO_UDS.items():
            if uds == uds_service:
                return kwp
        return uds_service


__all__ = ["KWP2000Handler", "KWP_TO_UDS", "HEADER_FORMATS"]
