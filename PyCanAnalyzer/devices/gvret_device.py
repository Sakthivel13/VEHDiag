"""GVRET Device Implementation - RESTful CAN Interface."""
import requests
import json
import time
from typing import Iterator, Optional
from core.core import CANFrame


class GVRETDevice:
    """GVRET (Great Valley Research Embedded Toolkit) device for CAN communication via REST API."""
    """GVRET (Great Valley Research Embedded Toolkit) device for CAN communication via REST API."""

    def __init__(self, url: str = "http://localhost:18888", bitrate: int = 500000):
        self.url = url.rstrip('/')
        self.bitrate = bitrate
        self.session = requests.Session()
        self.connected = False
        self.last_frame_time = 0

    def connect(self) -> None:
        """Connect to GVRET device via REST API."""
        try:
            # Test connection
            response = self.session.get(f"{self.url}/status", timeout=5)
            response.raise_for_status()

            # Set bitrate if supported
            try:
                self.session.post(f"{self.url}/setBitrate", json={"bitrate": self.bitrate}, timeout=5)
            except:
                pass  # Bitrate setting might not be supported

            self.connected = True
            print(f"Connected to GVRET at {self.url}")

        except requests.RequestException as e:
            raise ConnectionError(f"Failed to connect to GVRET at {self.url}: {e}")

    def disconnect(self) -> None:
        """Disconnect from GVRET device."""
        self.connected = False
        self.session.close()
        print("Disconnected from GVRET")

    def read_frames(self) -> Iterator[CANFrame]:
        """Read CAN frames from GVRET device."""
        if not self.connected:
            return

        try:
            # Get frames from GVRET
            response = self.session.get(f"{self.url}/frames", timeout=1)
            if response.status_code == 200:
                frames_data = response.json()

                for frame_data in frames_data:
                    # Parse GVRET frame format
                    can_id = frame_data.get('id', 0)
                    data = bytes(frame_data.get('data', []))
                    timestamp = frame_data.get('timestamp', time.time())

                    yield CANFrame(
                        timestamp=timestamp,
                        can_id=can_id,
                        dlc=len(data),
                        data=data
                    )

        except requests.RequestException:
            # Connection might be lost, but don't raise exception in iterator
            pass
        except (json.JSONDecodeError, KeyError):
            # Invalid response format
            pass

    def send_frame(self, frame: CANFrame) -> None:
        """Send CAN frame via GVRET device."""
        if not self.connected:
            return

        try:
            frame_data = {
                'id': frame.can_id,
                'data': list(frame.data),
                'extended': False  # TODO: detect extended ID
            }

            response = self.session.post(f"{self.url}/sendFrame", json=frame_data, timeout=1)
            response.raise_for_status()

        except requests.RequestException:
            # Frame send failed, but don't raise exception
            pass

    def get_status(self) -> dict:
        """Get GVRET device status."""
        if not self.connected:
            return {'connected': False}

        try:
            response = self.session.get(f"{self.url}/status", timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            return {'connected': False, 'error': 'Connection failed'}