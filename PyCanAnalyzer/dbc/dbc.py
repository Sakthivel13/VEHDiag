"""DBC (Database CAN) Support."""
import cantools
from typing import Dict, List, Optional
from core.core import CANFrame, Signal


class DBCManager:
    def __init__(self):
        self.databases: Dict[str, cantools.Database] = {}

    def load_dbc(self, file_path: str, name: str) -> None:
        """Load a DBC file."""
        try:
            db = cantools.database.load_file(file_path)
            self.databases[name] = db
            print(f"Loaded DBC {name} from {file_path}")
        except Exception as e:
            print(f"Failed to load DBC {file_path}: {e}")

    def decode_frame(self, frame: CANFrame, db_name: str = None) -> Dict[str, any]:
        """Decode a CAN frame using DBC."""
        if db_name not in self.databases:
            return {}

        db = self.databases[db_name]
        try:
            message = db.get_message_by_frame_id(frame.can_id)
            if message:
                data = db.decode_message(frame.can_id, frame.data)
                return data
        except Exception:
            pass
        return {}

    def encode_frame(self, can_id: int, signals: Dict[str, any], db_name: str = None) -> Optional[bytes]:
        """Encode signals into CAN frame data."""
        if db_name not in self.databases:
            return None

        db = self.databases[db_name]
        try:
            data = db.encode_message(can_id, signals)
            return data
        except Exception:
            return None

    def get_message_signals(self, can_id: int, db_name: str = None) -> List[str]:
        """Get signal names for a message."""
        if db_name not in self.databases:
            return []

        db = self.databases[db_name]
        try:
            message = db.get_message_by_frame_id(can_id)
            if message:
                return [signal.name for signal in message.signals]
        except Exception:
            pass
        return []

    def get_loaded_dbcs(self) -> List[str]:
        """Get list of loaded DBC names."""
        return list(self.databases.keys())