"""CAN FD protocol handler.

CAN FD reuses the whole classic CAN implementation and only changes the frame
capacity, the DLC encoding, the bit rate switch flag and the ISO-TP escape
sequence handling.
"""
from __future__ import annotations

import logging
from typing import Any

from ....core.enums.protocol_enums import MessageDirection, ProtocolType
from ....core.event_bus import EventBus, EventType
from ....core.interfaces.i_vci_driver import IVCIDriver
from ....core.models.message_model import BusMessage
from ...isotp_handler import fd_padded_length
from .can_protocol import CANProtocol

_logger = logging.getLogger(__name__)


class CANFDProtocol(CANProtocol):
    """UDS over CAN FD with up to 64 byte frames.

    Args:
        driver: VCI driver used to send and receive raw frames.
        config: Same keys as :class:`CANProtocol` plus ``data_bitrate`` and
            ``bitrate_switch``.
        event_bus: Bus used to publish TX/RX notifications.
    """

    def __init__(
        self,
        driver: IVCIDriver,
        config: dict[str, Any] | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        """Configure the ISO-TP engine for 64 byte frames."""
        super().__init__(driver, config, event_bus)
        self.data_bitrate = int(self.config.get("data_bitrate", 2_000_000))
        self.bitrate_switch = bool(self.config.get("bitrate_switch", True))
        self.isotp_config.can_fd = True
        self.isotp_config.max_frame_size = 64

    @property
    def protocol_type(self) -> ProtocolType:
        """Return :attr:`ProtocolType.CAN_FD`."""
        return ProtocolType.CAN_FD

    def _send_raw_frame(self, data: bytes) -> None:
        """Transmit one CAN FD frame, padded to a legal DLC length."""
        padded = data
        if self.isotp_config.tx_padding:
            target = fd_padded_length(len(data))
            if len(padded) < target:
                padded = padded + bytes([self.isotp_config.padding_byte & 0xFF]) * (
                    target - len(padded)
                )
        message = BusMessage(
            data=padded,
            arbitration_id=self.functional_id if self._tx_functional else self.tx_id,
            direction=MessageDirection.TX,
            protocol=ProtocolType.CAN_FD,
            is_extended_id=self.extended_id,
            is_fd=True,
            bitrate_switch=self.bitrate_switch,
        )
        self.driver.send(message)
        self.bus.publish(EventType.COMM_MESSAGE_TX, {"message": message}, type(self).__name__)

    def get_protocol_info(self) -> dict[str, Any]:
        """Return the CAN information plus the FD specific parameters."""
        info = super().get_protocol_info()
        info.update({"data_bitrate": self.data_bitrate, "bitrate_switch": self.bitrate_switch})
        return info


__all__ = ["CANFDProtocol"]
