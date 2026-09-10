"""Frame Storage Engine."""
import csv
import os
from typing import List, Iterator
from core.core import FrameBatch, CANFrame


class FrameStore:
    def __init__(self, config):
        self.config = config
        self.path = config.get("storage_path", "data/frames.parquet")

    def append_batch(self, batch: FrameBatch):
        print(f"Appending {len(batch)} frames to {self.path} (scaffold)")


class FrameIndex:
    def __init__(self):
        self.index = {}

    def build(self, frames):
        pass


class FrameCache:
    def __init__(self):
        self.cache = {}

    def get(self, key):
        return self.cache.get(key)


class ParquetStorage:
    def write(self, table, path: str):
        print(f"Writing parquet to {path} (scaffold)")


class MMapStorage:
    def __init__(self, path: str):
        self.path = path

    def write(self, data: bytes):
        pass


class SignalStore:
    def __init__(self, path: str):
        self.path = path

    def save(self, signals):
        print(f"Saving {len(signals)} signals to {self.path} (scaffold)")


class FrameFileIO:
    """Handle loading/saving CAN frames in various formats."""

    @staticmethod
    def load_csv(file_path: str) -> Iterator[CANFrame]:
        """Load frames from CSV format: timestamp,id,d0,d1,d2,d3,d4,d5,d6,d7"""
        with open(file_path, 'r') as f:
            reader = csv.reader(f)
            next(reader, None)  # Skip header if present
            for row in reader:
                if len(row) >= 9:
                    try:
                        timestamp = float(row[0])
                        can_id = int(row[1], 16) if row[1].startswith('0x') else int(row[1])
                        data = bytes([int(x, 16) if x.startswith('0x') else int(x) for x in row[2:10]])
                        yield CANFrame(timestamp=timestamp, can_id=can_id, dlc=len(data), data=data)
                    except ValueError:
                        continue

    @staticmethod
    def save_csv(frames: List[CANFrame], file_path: str) -> None:
        """Save frames to CSV format."""
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'id', 'd0', 'd1', 'd2', 'd3', 'd4', 'd5', 'd6', 'd7'])
            for frame in frames:
                row = [frame.timestamp, f"0x{frame.can_id:03X}"]
                row.extend([f"0x{b:02X}" for b in frame.data])
                row.extend(['0x00'] * (8 - len(frame.data)))  # Pad to 8 bytes
                writer.writerow(row)

    @staticmethod
    def load_gvret(file_path: str) -> Iterator[CANFrame]:
        """Load frames from GVRET format."""
        # GVRET format: timestamp(4), id(4), dlc(1), data(8)
        with open(file_path, 'rb') as f:
            while True:
                data = f.read(17)  # 4 + 4 + 1 + 8
                if len(data) < 17:
                    break
                timestamp = int.from_bytes(data[0:4], 'little') / 1000000.0
                can_id = int.from_bytes(data[4:8], 'little')
                dlc = data[8]
                frame_data = data[9:9+dlc]
                yield CANFrame(timestamp=timestamp, can_id=can_id, dlc=dlc, data=frame_data)

    @staticmethod
    def save_gvret(frames: List[CANFrame], file_path: str) -> None:
        """Save frames to GVRET format."""
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'wb') as f:
            for frame in frames:
                f.write(int(frame.timestamp * 1000000).to_bytes(4, 'little'))
                f.write(frame.can_id.to_bytes(4, 'little'))
                f.write(frame.dlc.to_bytes(1, 'little'))
                f.write(frame.data.ljust(8, b'\x00'))

    @staticmethod
    def load_busmaster(file_path: str) -> Iterator[CANFrame]:
        """Load frames from BusMaster format."""
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('***'):
                    continue
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        timestamp = float(parts[0])
                        direction = parts[1]  # Rx/Tx
                        can_id = int(parts[2], 16)
                        dlc = int(parts[3])
                        data = bytes([int(x, 16) for x in parts[4:4+dlc]])
                        yield CANFrame(timestamp=timestamp, can_id=can_id, dlc=dlc, data=data)
                    except ValueError:
                        continue

    @staticmethod
    def save_busmaster(frames: List[CANFrame], file_path: str) -> None:
        """Save frames to BusMaster format."""
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w') as f:
            f.write("***BUSMASTER Ver 3.0.0***\n")
            f.write("***PROTOCOL CAN***\n")
            f.write("***NOTE: PLEASE DO NOT EDIT THIS LOG FILE***\n")
            f.write("***START DATE AND TIME***\n")
            f.write("***END DATE AND TIME***\n")
            f.write("***START DATA***\n")
            for frame in frames:
                data_str = ' '.join([f"{b:02X}" for b in frame.data])
                f.write(f"{frame.timestamp:.6f} Rx {frame.can_id:03X} {frame.dlc} {data_str}\n")
            f.write("***END DATA***\n")

    @staticmethod
    def load_candump(file_path: str) -> Iterator[CANFrame]:
        """Load frames from candump format."""
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or not line.startswith('('):
                    continue
                # Format: (timestamp) interface id#data
                try:
                    timestamp_end = line.find(')')
                    timestamp = float(line[1:timestamp_end])
                    rest = line[timestamp_end+1:].strip()
                    id_end = rest.find('#')
                    can_id = int(rest[:id_end], 16)
                    data_str = rest[id_end+1:]
                    data = bytes([int(data_str[i:i+2], 16) for i in range(0, len(data_str), 2)])
                    yield CANFrame(timestamp=timestamp, can_id=can_id, dlc=len(data), data=data)
                except ValueError:
                    continue

    @staticmethod
    def save_candump(frames: List[CANFrame], file_path: str, interface: str = 'can0') -> None:
        """Save frames to candump format."""
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w') as f:
            for frame in frames:
                data_str = ''.join([f"{b:02X}" for b in frame.data])
                f.write(f"({frame.timestamp:.6f}) {interface} {frame.can_id:03X}#{data_str}\n")


class FrameIndex:
    def __init__(self):
        self.index = {}

    def build(self, frames):
        pass


class FrameCache:
    def __init__(self):
        self.cache = {}

    def get(self, key):
        return self.cache.get(key)


class ParquetStorage:
    def write(self, table, path: str):
        print(f"Writing parquet to {path} (scaffold)")


class MMapStorage:
    def __init__(self, path: str):
        self.path = path

    def write(self, data: bytes):
        pass


class SignalStore:
    def __init__(self, path: str):
        self.path = path

    def save(self, signals):
        print(f"Saving {len(signals)} signals to {self.path} (scaffold)")