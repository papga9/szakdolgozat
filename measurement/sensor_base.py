import threading
from collections import deque


class SensorBase():
    def __init__(self):
        self._lock = threading.Lock()

    def start(self):
        pass

    def stop(self):
        pass

    def get_value(self):
        with self._lock:
            return self._current_value

    def set_window_size(self, window_size: int):
        """Set window size for rolling mean (number of samples)."""
        if window_size <= 0:
            return
        with self._lock:
            self._window_size = int(window_size)
            recent = list(self._samples)[-self._window_size:]
            self._samples = deque(recent, maxlen=self._window_size)

    def get_value_mean(self):
        """Return arithmetic mean of the past N samples (N = current window size)."""
        with self._lock:
            if not self._samples:
                return 0.0
            return sum(self._samples) / len(self._samples)
