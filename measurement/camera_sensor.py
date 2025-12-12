import time
import threading
from collections import deque

import cv2

from measurement.sensor_base import SensorBase


class CameraSensor(SensorBase):
    def __init__(self, src=0, window_size: int = 50,
                 hsv_s_min: int = 100, hsv_v_min: int = 60,
                 resize_to: tuple[int, int] | None = None,
                 normalize: bool = True):
        self.src = src
        self.hsv_s_min = int(hsv_s_min)
        self.hsv_v_min = int(hsv_v_min)
        self.resize_to = resize_to
        self.normalize = bool(normalize)

        self._running = False
        self._thread = None
        self._cap = None
        self._current_value = 0.0
        self._window_size = max(1, int(window_size))
        self._samples = deque(maxlen=self._window_size)

    def start(self):
        if self._running:
            return
        if cv2 is None:
            print("CAMERA ERROR: OpenCV (cv2) is not available.")
            return
        self._cap = cv2.VideoCapture(self.src)
        if not self._cap or not self._cap.isOpened():
            print("CAMERA ERROR: Unable to open video source", self.src)
            self._cap = None
            return
        self._running = True
        self._thread = threading.Thread(target=self._camera_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        if self._cap:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

    def _camera_loop(self):
        try:
            while self._running and self._cap and self._cap.isOpened():
                ok, frame = self._cap.read()
                if not ok or frame is None:
                    time.sleep(0.02)
                    continue

                if self.resize_to is not None:
                    try:
                        frame = cv2.resize(frame, self.resize_to)
                    except Exception:
                        pass

                hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                # Red in HSV wraps: low hue [0..10] and high hue [160..179]
                lower_red1 = (0, self.hsv_s_min, self.hsv_v_min)
                upper_red1 = (10, 255, 255)
                lower_red2 = (160, self.hsv_s_min, self.hsv_v_min)
                upper_red2 = (179, 255, 255)
                mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
                mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
                mask = cv2.bitwise_or(mask1, mask2)

                red_pixels = int(cv2.countNonZero(mask))
                if self.normalize:
                    total_pixels = mask.shape[0] * mask.shape[1]
                    value = red_pixels / total_pixels if total_pixels else 0.0
                else:
                    value = float(red_pixels)

                with self._lock:
                    self._current_value = value
                    self._samples.append(value)

                # Small delay to reduce CPU usage
                time.sleep(0.01)
        except Exception as e:
            print(f"CAMERA SENSOR ERROR: {e}")
            self._running = False
