"""Hardware Interface Layer."""
from abc import ABC, abstractmethod
from typing import Iterator, Optional
import can
from core.core import CANFrame
from .gvret_device import GVRETDevice


class BaseDevice(ABC):
    @abstractmethod
    def connect(self) -> None:
        pass

    @abstractmethod
    def disconnect(self) -> None:
        pass

    @abstractmethod
    def read_frames(self) -> Iterator[CANFrame]:
        yield from ()

    @abstractmethod
    def send_frame(self, frame: CANFrame) -> None:
        pass


class DeviceManager:
    def __init__(self, config):
        self.config = config
        self.devices = []
        self.connected_devices = []

    def register(self, dev: BaseDevice) -> None:
        self.devices.append(dev)

    def connect_all(self) -> None:
        for dev in self.devices:
            try:
                dev.connect()
                self.connected_devices.append(dev)
            except Exception as e:
                print(f"Failed to connect device: {e}")

    def disconnect_all(self) -> None:
        for dev in self.connected_devices:
            try:
                dev.disconnect()
            except Exception as e:
                print(f"Failed to disconnect device: {e}")
        self.connected_devices.clear()

    def all_frames(self):
        for d in self.connected_devices:
            try:
                for f in d.read_frames():
                    yield f
            except Exception:
                continue

    def send_frame(self, frame: CANFrame) -> None:
        for d in self.connected_devices:
            try:
                d.send_frame(frame)
            except Exception:
                continue


class CANBusDevice(BaseDevice):
    """Base class for python-can based devices."""
    def __init__(self, bus_config: dict):
        self.bus_config = bus_config
        self.bus: Optional[can.Bus] = None

    def connect(self) -> None:
        try:
            self.bus = can.Bus(**self.bus_config)
        except Exception as e:
            raise ConnectionError(f"Failed to connect to CAN bus: {e}")

    def disconnect(self) -> None:
        if self.bus:
            self.bus.shutdown()
            self.bus = None

    def read_frames(self) -> Iterator[CANFrame]:
        if not self.bus:
            return
        while True:
            try:
                msg = self.bus.recv(timeout=0.1)
                if msg:
                    yield CANFrame(
                        timestamp=msg.timestamp,
                        can_id=msg.arbitration_id,
                        dlc=msg.dlc,
                        data=bytes(msg.data)
                    )
            except can.CanError:
                break

    def send_frame(self, frame: CANFrame) -> None:
        if self.bus:
            msg = can.Message(
                arbitration_id=frame.can_id,
                data=frame.data,
                is_extended_id=False  # TODO: detect extended ID
            )
            self.bus.send(msg)


class SocketCANDevice(CANBusDevice):
    def __init__(self, interface: str = 'can0'):
        super().__init__({
            'interface': 'socketcan',
            'channel': interface,
            'receive_own_messages': True
        })


class PCANDevice(CANBusDevice):
    def __init__(self, channel: str = 'PCAN_USBBUS1'):
        super().__init__({
            'interface': 'pcan',
            'channel': channel,
            'bitrate': 500000
        })


class VectorDevice(CANBusDevice):
    def __init__(self, channel: int = 0, app_name: str = 'PyCANAnalyzer', bitrate: int = 500000):
        super().__init__({
            'interface': 'vector',
            'channel': channel,
            'app_name': app_name,
            'bitrate': bitrate
        })


class KvaserDevice(CANBusDevice):
    """Kvaser CAN interface support."""
    def __init__(self, channel: int = 0, bitrate: int = 500000):
        super().__init__({
            'interface': 'kvaser',
            'channel': channel,
            'bitrate': bitrate
        })


class VirtualCANDevice(BaseDevice):
    """Virtual device for testing."""
    def __init__(self, channel: str = 'vcan0', rate_hz: float = 1000.0):
        self.channel = channel
        self.rate_hz = rate_hz
        self.bus = None

    def connect(self) -> None:
        self.bus = can.Bus(interface='virtual', channel=self.channel)

    def disconnect(self) -> None:
        if self.bus:
            self.bus.shutdown()
            self.bus = None

    def read_frames(self) -> Iterator[CANFrame]:
        if not self.bus:
            return
        while True:
            try:
                msg = self.bus.recv(timeout=0.1)
                if msg:
                    yield CANFrame(
                        timestamp=msg.timestamp,
                        can_id=msg.arbitration_id,
                        dlc=msg.dlc,
                        data=bytes(msg.data)
                    )
            except can.CanError:
                break

    def send_frame(self, frame: CANFrame) -> None:
        if self.bus:
            msg = can.Message(
                arbitration_id=frame.can_id,
                data=frame.data,
                is_extended_id=False
            )
            self.bus.send(msg)


# Legacy GVRET support (placeholder)
class GVRETDevice(BaseDevice):
    def __init__(self, url: str):
        self.url = url

    def connect(self):
        print(f"Connecting to GVRET at {self.url} (scaffold)")

    def disconnect(self):
        print("Disconnecting GVRET (scaffold)")

    def read_frames(self):
        return iter(())

    def send_frame(self, frame: CANFrame):
        pass


class GVRETProtocol:
    @staticmethod
    def parse_packet(data: bytes):
        return {"raw": data}