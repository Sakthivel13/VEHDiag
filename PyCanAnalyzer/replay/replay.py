"""CAN Replay Engine."""
class ReplayController:
    def __init__(self):
        self.playing = False

    def play(self, frames, speed: float = 1.0):
        self.playing = True
        for f in frames:
            if not self.playing:
                break

    def stop(self):
        self.playing = False


class ReplayScheduler:
    def schedule(self, frames, start_time=None):
        return frames


class ReplayDeviceInterface:
    def send_frame(self, frame):
        pass


class ReplayFilters:
    @staticmethod
    def filter_frames(frames, predicate):
        for f in frames:
            if predicate(f):
                yield f