import time
import threading
from smbus2 import SMBus, i2c_msg
from collections import deque

try:
    import cv2
except Exception:
    cv2 = None


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


class VoltageSensor(SensorBase):
    def __init__(self, i2c_addr=0x68, channel=0, res_bits=12, vref=2.048, board_scale=(5.06/2.048), window_size: int = 50):
        self.i2c_addr = i2c_addr
        self.channel = channel
        self.res_bits = res_bits
        self.vref = vref
        self.board_scale = board_scale

        # Belső változók
        self._running = False
        self._thread = None
        self._current_value = 0.0
        # Rolling buffer for mean over past N samples
        self._window_size = max(1, int(window_size))
        self._samples = deque(maxlen=self._window_size)

        # Konfigurációs értékek számítása
        if self.res_bits == 12:
            self._rb_cfg = 0b00
            self._denom = 2**11 - 1
            self._wait = 0.005
        elif self.res_bits == 14:
            self._rb_cfg = 0b01
            self._denom = 2**13 - 1
            self._wait = 0.02
        elif self.res_bits == 16:
            self._rb_cfg = 0b10
            self._denom = 2**15 - 1
            self._wait = 0.07
        elif self.res_bits == 18:
            self._rb_cfg = 0b11
            self._denom = 2**17 - 1
            self._wait = 0.3
        else:
            self._rb_cfg = 0b10
            self._denom = 2**15 - 1
            self._wait = 0.07

    def start(self):
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._sensor_loop, daemon=True)
            self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)

    def _sensor_loop(self):
        try:
            with SMBus(1) as bus:
                while self._running:
                    # Config byte összeállítása
                    config_byte = ((self.channel & 0x03) << 5) | (1 << 7) | (self._rb_cfg << 2) | 0b00

                    try:
                        bus.write_byte(self.i2c_addr, config_byte)
                        time.sleep(self._wait + 0.001)

                        read = i2c_msg.read(self.i2c_addr, 3)
                        bus.i2c_rdwr(read)
                        data = list(read)
                        msb, lsb, cfg = data

                        raw = (msb << 8) | lsb
                        if raw & 0x8000:
                            raw -= 1 << 16

                        V_internal = (raw / self._denom) * self.vref
                        Vin_est = V_internal * self.board_scale

                        with self._lock:
                            self._current_value = Vin_est
                            # Update mean buffer
                            self._samples.append(Vin_est)

                    except OSError:
                        # I2C hiba esetén nem állunk meg, csak kihagyjuk a kört
                        pass

                    time.sleep(0.01)
        except Exception as e:
            print(f"SZENZOR HIBA: {e}")
            self._running = False


class CameraSensor(SensorBase):
    def __init__(self, src=0, window_size: int = 50,
                 hsv_s_min: int = 100, hsv_v_min: int = 60,
                 resize_to: tuple[int, int] | None = None,
                 normalize: bool = True):
        """
        Camera-based intensity sensor that measures the amount of red pixels.

        - Captures frames from `src` (e.g., 0 for default webcam).
        - Segments red in HSV (two ranges for hue wrap-around).
        - Counts thresholded red pixels and exposes it as the sensor value.
          If `normalize` is True, value is fraction in [0,1]; otherwise, raw count.
        - Maintains a rolling window to compute mean via `get_value_mean()`.
        """
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
