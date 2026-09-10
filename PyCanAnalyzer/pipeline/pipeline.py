"""Ultra-Fast Frame Pipeline."""
from collections import deque
from typing import Optional
from core.core import CANFrame, FrameBatch
from devices.devices import DeviceManager


class SharedRingBuffer:
    def __init__(self, capacity: int = 65536):
        self._buf = deque(maxlen=capacity)

    def push(self, item) -> None:
        self._buf.append(item)

    def pop_batch(self, max_items: int = 1024):
        out = []
        for _ in range(min(len(self._buf), max_items)):
            out.append(self._buf.popleft())
        return out

    def __len__(self):
        return len(self._buf)


class FramePool:
    def __init__(self, size: int = 4096):
        self.size = size

    def get(self):
        return None

    def release(self, obj):
        pass


class DeviceReader:
    def __init__(self, device_manager: DeviceManager, ring: SharedRingBuffer):
        self.device_manager = device_manager
        self.ring = ring

    def run_once(self):
        for f in self.device_manager.all_frames():
            self.ring.push(f)


class PacketDecoder:
    @staticmethod
    def decode_packet(pkt) -> CANFrame:
        return CANFrame(timestamp=pkt.get("timestamp", 0.0), can_id=pkt.get("id", 0), dlc=len(pkt.get("data", b"")), data=pkt.get("data", b""))


class BatchBuilder:
    def __init__(self, ring: SharedRingBuffer, batch_size: int = 1024):
        self.ring = ring
        self.batch_size = batch_size

    def build(self) -> FrameBatch:
        items = self.ring.pop_batch(self.batch_size)
        batch = FrameBatch(items)
        return batch


class FrameDispatcher:
    def __init__(self):
        self.handlers = []

    def register(self, fn):
        self.handlers.append(fn)

    def dispatch(self, batch):
        for h in self.handlers:
            h(batch)


class PipelineScheduler:
    def __init__(self):
        self.running = False

    def start(self):
        self.running = True
        while self.running:
            import time
            time.sleep(0.1)

    def stop(self):
        self.running = False


class PipelineMonitor:
    def __init__(self):
        self.metrics = {}

    def record(self, key, value):
        self.metrics.setdefault(key, []).append(value)


class Pipeline:
    def __init__(self, device_manager: DeviceManager, config):
        self.device_manager = device_manager
        self.config = config
        self.frames = []  # Frame buffer
        self.ring = SharedRingBuffer(config.get("ring_buffer_size", 65536))
        self.reader = DeviceReader(device_manager, self.ring)
        self.builder = BatchBuilder(self.ring, config.get("batch_size", 1024))
        self.dispatcher = FrameDispatcher()
        self.scheduler = PipelineScheduler()
        self.monitor = PipelineMonitor()

    def add_frame(self, frame):
        self.frames.append(frame)

    def get_frames(self):
        return self.frames

    def start(self):
        self.scheduler.start()

    def stop(self):
        self.scheduler.stop()