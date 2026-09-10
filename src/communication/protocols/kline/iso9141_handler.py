"""ISO 9141-2 specific K-Line handler."""
from __future__ import annotations

from typing import Any

from ....core.enums.protocol_enums import KLineInitType
from ....core.event_bus import EventBus
from ....core.interfaces.i_vci_driver import IVCIDriver
from .kline_protocol import KLineProtocol
from .kline_timing import KLineTiming

#: Keyword bytes reported by an ISO 9141-2 compliant ECU.
ISO9141_KEYWORDS: tuple[int, int] = (0x08, 0x08)


class ISO9141Handler(KLineProtocol):
    """K-Line handler forcing ISO 9141-2 framing and five baud initialisation.

    The header is the fixed three byte ``0x68 <target> <source>`` form and the
    initialisation always uses the 5 baud address byte ``0x33``.
    """

    def __init__(
        self,
        driver: IVCIDriver | None = None,
        config: dict[str, Any] | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        """Force five baud init and ISO 9141 framing."""
        merged = dict(config or {})
        merged.setdefault("address_byte", 0x33)
        merged["init_type"] = KLineInitType.FIVE_BAUD.value
        super().__init__(driver, merged, event_bus)
        self.use_kwp_framing = False
        self.timing = KLineTiming.iso9141()

    def is_compliant(self) -> bool:
        """Return ``True`` when the ECU reported the ISO 9141-2 keywords."""
        return bool(self.init_result and self.init_result.key_bytes == ISO9141_KEYWORDS)


__all__ = ["ISO9141Handler", "ISO9141_KEYWORDS"]
