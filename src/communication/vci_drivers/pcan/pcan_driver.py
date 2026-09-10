"""PEAK PCAN driver.

Two implementations are provided:

* :class:`PythonCanDriver` - a generic adapter around :mod:`can` that works for
  every backend python-can supports (``pcan``, ``socketcan``, ``vector``,
  ``kvaser``, ``neovi``, ...). This is the recommended path because it is
  cross-platform and needs no ctypes plumbing.
* :class:`PCANDriver` - a thin specialisation that selects the ``pcan``
  backend and translates channel indices into ``PCAN_USBBUSx`` handles, falling
  back to the raw :class:`PCANBasicWrapper` when python-can is missing.
"""
from __future__ import annotations

import logging
from typing import Any

from ....core.enums.protocol_enums import ProtocolType
from ....core.enums.vci_enums import VCICapability, VCIType
from ....core.event_bus import EventBus
from ....core.exceptions import ConnectionFailedError, DriverNotFoundError, SendError
from ....core.models.message_model import BusMessage
from ....core.models.vci_model import VCIChannelConfig, VCIDeviceInfo
from ..base_vci_driver import BaseVCIDriver

_logger = logging.getLogger(__name__)


class PythonCanDriver(BaseVCIDriver):
    """Generic VCI driver built on top of :mod:`can`.

    Args:
        interface: python-can backend name, e.g. ``"pcan"`` or ``"socketcan"``.
        config: Channel configuration.
        event_bus: Bus used for connection notifications.
        vci_type: Hardware family reported to the UI.
        **bus_kwargs: Extra keyword arguments forwarded to ``can.Bus``.
    """

    vci_type = VCIType.SOCKETCAN
    capabilities = frozenset(
        {VCICapability.CAN, VCICapability.CAN_FD, VCICapability.ERROR_FRAMES}
    )

    def __init__(
        self,
        interface: str = "socketcan",
        config: VCIChannelConfig | None = None,
        event_bus: EventBus | None = None,
        vci_type: VCIType | None = None,
        **bus_kwargs: Any,
    ) -> None:
        """Store the backend selection without opening the channel."""
        super().__init__(config, event_bus)
        self.interface = interface
        self.bus_kwargs = bus_kwargs
        if vci_type is not None:
            self.vci_type = vci_type
        self._bus: Any = None

    def _import_can(self) -> Any:
        """Import :mod:`can`, raising a platform error when it is missing.

        Raises:
            DriverNotFoundError: python-can is not installed.
        """
        try:
            import can  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - dependency is declared
            raise DriverNotFoundError(
                "python-can is required for hardware interfaces",
                {"pip": "pip install python-can"},
            ) from exc
        return can

    #: Backends whose ``channel`` argument must be an integer index.
    #:
    #: Kvaser's CANlib declares ``channel: int`` and indexes into the device
    #: table with it, so handing it the string ``"1"`` raises deep inside the
    #: vendor library with an unhelpful message.
    NUMERIC_CHANNEL: frozenset[str] = frozenset({"kvaser", "vector", "pcan"})

    #: Backends whose ``channel`` argument is a kernel interface *name*.
    #:
    #: ``SocketcanBus`` ends up calling ``sock.bind((channel,))``, which needs
    #: ``"can0"``/``"vcan0"``; a bare index binds to a non-existent interface.
    NAMED_CHANNEL: dict[str, str] = {"socketcan": "can", "socketcand": "can"}

    @staticmethod
    def _as_index(value: Any) -> int | None:
        """Return *value* as an integer channel index, or ``None``.

        The connection panel stores the channel as the combo box *text*, so a
        perfectly ordinary selection arrives here as ``"1"`` rather than ``1``.
        Every backend-specific translation used to be skipped for those
        strings, which made hardware connections fail while the virtual
        driver - which ignores the channel - kept working.
        """
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
        return None

    def _channel_argument(self) -> Any:
        """Return the channel value in the form the backend expects.

        Example:
            >>> from src.core.models.vci_model import VCIChannelConfig
            >>> d = PythonCanDriver("socketcan", VCIChannelConfig(channel="0"))
            >>> d._channel_argument()
            'can0'
            >>> PythonCanDriver("kvaser", VCIChannelConfig(channel="2"))._channel_argument()
            2
        """
        channel = self.config.channel
        index = self._as_index(channel)
        prefix = self.NAMED_CHANNEL.get(self.interface)
        if prefix is not None:
            # Already a name such as "can0", "vcan0" or "slcan0": keep it.
            if index is None:
                return channel
            return f"{prefix}{index}"
        if index is not None and self.interface in self.NUMERIC_CHANNEL:
            return index
        return channel

    #: Backends that configure the bitrate outside python-can.
    #:
    #: SocketCAN takes its timing from the kernel link (``ip link set can0 up
    #: type can bitrate 500000``); passing ``bitrate`` to :class:`can.Bus`
    #: silently lands in ``**kwargs`` and is ignored, which used to make the
    #: platform look connected while running at the wrong speed.
    NO_BITRATE_KWARG: frozenset[str] = frozenset(
        {"socketcan", "socketcand", "virtual", "udp_multicast"}
    )

    #: Backends that reject an explicit ``data_bitrate`` keyword.
    NO_DATA_BITRATE_KWARG: frozenset[str] = frozenset(
        {"socketcan", "socketcand", "kvaser", "virtual"}
    )

    def _build_bus_kwargs(self) -> dict[str, Any]:
        """Return the keyword arguments handed to :class:`can.Bus`.

        Every backend advertises a slightly different constructor, so the
        arguments are filtered per backend instead of being passed blindly.

        Returns:
            The keyword arguments for the configured backend.
        """
        kwargs: dict[str, Any] = {
            "interface": self.interface,
            "channel": self._channel_argument(),
            "receive_own_messages": False,
        }
        if self.interface not in self.NO_BITRATE_KWARG:
            kwargs["bitrate"] = int(self.config.bitrate)
        if self.config.protocol is ProtocolType.CAN_FD:
            kwargs["fd"] = True
            if self.interface not in self.NO_DATA_BITRATE_KWARG:
                kwargs["data_bitrate"] = int(self.config.data_bitrate)
        if self.config.listen_only:
            kwargs["listen_only"] = True
        if self.config.sample_point:
            kwargs.setdefault("sample_point", float(self.config.sample_point))
        kwargs.update(self.config.extra)
        kwargs.update(self.bus_kwargs)
        return kwargs

    def _connection_hint(self) -> str:
        """Return an actionable hint shown when the channel cannot be opened.

        The SocketCAN hint names the actual link and bitrate so the operator
        can paste the command straight into a terminal.
        """
        if self.interface in self.NAMED_CHANNEL:
            return (
                f"bring the link up: sudo ip link set {self._channel_argument()} "
                f"up type can bitrate {int(self.config.bitrate)}"
            )
        return {
            "pcan": "install the PEAK driver and check the PCAN_USBBUSx index",
            "vector": "assign the channel to the application name "
                      "'VehicleDiagnosticsPlatform' in Vector Hardware Config",
            "kvaser": "install Kvaser CANlib and check the channel index",
            "neovi": "install python-ics and the Intrepid drivers",
        }.get(self.interface, "check that the vendor driver is installed")

    def _do_connect(self) -> None:
        """Open the python-can bus.

        Raises:
            ConnectionFailedError: The backend refused to open the channel.
        """
        can = self._import_can()
        kwargs = self._build_bus_kwargs()
        _logger.info(
            "opening %s channel %r (%s)",
            self.interface,
            kwargs.get("channel"),
            ", ".join(
                f"{k}={v}" for k, v in kwargs.items() if k not in ("interface", "channel")
            ),
        )
        try:
            self._bus = can.Bus(**kwargs)
        except Exception as exc:  # noqa: BLE001 - normalise backend errors
            raise ConnectionFailedError(
                f"could not open the {self.interface} channel "
                f"{kwargs.get('channel', self.config.channel)!r}",
                {
                    "cause": str(exc),
                    "interface": self.interface,
                    "channel": kwargs.get("channel"),
                    "bitrate": self.config.bitrate,
                    "hint": self._connection_hint(),
                },
            ) from exc
        if self.interface == "socketcan":
            _logger.warning(
                "SocketCAN takes its bitrate from the kernel; run "
                "'sudo ip link set %s up type can bitrate %d' if the link is down",
                kwargs.get("channel"),
                self.config.bitrate,
            )

    def _do_disconnect(self) -> None:
        """Shut the python-can bus down."""
        if self._bus is not None:
            try:
                self._bus.shutdown()
            finally:
                self._bus = None

    def _do_send(self, message: BusMessage) -> None:
        """Transmit one frame through python-can.

        Raises:
            SendError: The backend rejected the frame.
        """
        can = self._import_can()
        frame = can.Message(
            arbitration_id=message.arbitration_id,
            data=message.data,
            is_extended_id=message.is_extended_id,
            is_fd=message.is_fd,
            bitrate_switch=message.bitrate_switch,
        )
        try:
            self._bus.send(frame, timeout=1.0)
        except Exception as exc:  # noqa: BLE001
            self.status.error_count += 1
            raise SendError("failed to transmit a CAN frame", {"cause": str(exc)}) from exc

    def _do_receive(self, timeout: float) -> BusMessage | None:
        """Read the next frame from python-can."""
        if self._bus is None:
            return None
        frame = self._bus.recv(timeout)
        if frame is None:
            return None
        return BusMessage(
            data=bytes(frame.data or b""),
            arbitration_id=int(frame.arbitration_id),
            protocol=ProtocolType.CAN_FD if getattr(frame, "is_fd", False) else ProtocolType.CAN,
            timestamp=float(getattr(frame, "timestamp", 0.0)) or 0.0,
            channel=str(self.config.channel),
            is_extended_id=bool(frame.is_extended_id),
            is_fd=bool(getattr(frame, "is_fd", False)),
            bitrate_switch=bool(getattr(frame, "bitrate_switch", False)),
            is_error_frame=bool(getattr(frame, "is_error_frame", False)),
        )

    def _build_device_info(self) -> VCIDeviceInfo:
        """Return information gathered from the backend."""
        return VCIDeviceInfo(
            vci_type=self.vci_type,
            name=f"{self.interface} {self.config.channel}",
            channel_count=1,
            driver_version=getattr(self._bus, "channel_info", "") or self.interface,
            extra={"interface": self.interface},
        )

    def flush(self) -> None:
        """Drain the receive buffer of the backend."""
        while self._bus is not None and self._bus.recv(0) is not None:
            continue


class PCANDriver(PythonCanDriver):
    """PEAK PCAN-USB / PCAN-USB FD driver.

    Uses the python-can ``pcan`` backend when available; otherwise the raw
    :class:`~src.communication.vci_drivers.pcan.pcan_basic_wrapper.PCANBasicWrapper`
    is used so the platform still works on systems with only the PEAK SDK.
    """

    vci_type = VCIType.PCAN
    capabilities = frozenset(
        {
            VCICapability.CAN,
            VCICapability.CAN_FD,
            VCICapability.LISTEN_ONLY,
            VCICapability.ERROR_FRAMES,
            VCICapability.HARDWARE_TIMESTAMPS,
            VCICapability.BUS_STATISTICS,
        }
    )

    def __init__(
        self,
        config: VCIChannelConfig | None = None,
        event_bus: EventBus | None = None,
        **bus_kwargs: Any,
    ) -> None:
        """Select the ``pcan`` python-can backend."""
        super().__init__("pcan", config, event_bus, VCIType.PCAN, **bus_kwargs)

    def _channel_argument(self) -> Any:
        """Translate a numeric channel into a ``PCAN_USBBUSx`` handle.

        PEAK numbers its channels from one, and ``config/vci_profiles/
        pcan_profile.yaml`` lists them that way, so channel ``1`` must open
        ``PCAN_USBBUS1``. Channel ``0`` is accepted as a synonym for the first
        bus because the UI defaults numeric fields to zero.

        Example:
            >>> from src.core.models.vci_model import VCIChannelConfig
            >>> d = PCANDriver(VCIChannelConfig(channel=1))
            >>> d._channel_argument()
            'PCAN_USBBUS1'
            >>> PCANDriver(VCIChannelConfig(channel=0))._channel_argument()
            'PCAN_USBBUS1'
            >>> PCANDriver(VCIChannelConfig(channel=3))._channel_argument()
            'PCAN_USBBUS3'
            >>> PCANDriver(VCIChannelConfig(channel="PCAN_PCIBUS2"))._channel_argument()
            'PCAN_PCIBUS2'
            >>> PCANDriver(VCIChannelConfig(channel="2"))._channel_argument()
            'PCAN_USBBUS2'
        """
        channel = self.config.channel
        index = self._as_index(channel)
        if index is None:
            # A explicit handle such as "PCAN_PCIBUS2" is passed through.
            return channel
        return f"PCAN_USBBUS{max(1, index)}"

    def _build_device_info(self) -> VCIDeviceInfo:
        """Return PCAN specific device information."""
        info = super()._build_device_info()
        info.name = "PEAK PCAN-USB"
        info.vci_type = VCIType.PCAN
        return info


__all__ = ["PythonCanDriver", "PCANDriver"]
