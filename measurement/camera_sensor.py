import time
import threading
from collections import deque

import cv2
from picamera2 import Picamera2

from .sensor_base import SensorBase


class CameraSensor(SensorBase):
    def __init__(self, src=0, window_size: int = 50,
                 hsv_s_min: int = 100, hsv_v_min: int = 60,
                 resize_to: tuple[int, int] | None = None,
                 normalize: bool = True,
                 capture_size: tuple[int, int] | None = (1280, 720),
                 exposure_time_us: int | None = 100,
                 ae_enable: bool | None = None):
        SensorBase.__init__(self)

        self.src = src
        self.hsv_s_min = int(hsv_s_min)
        self.hsv_v_min = int(hsv_v_min)
        self.resize_to = resize_to
        self.normalize = bool(normalize)
        self.capture_size = capture_size
        # Camera control options
        self.exposure_time_us = exposure_time_us
        self.ae_enable = ae_enable

        self._running = False
        self._thread = None
        self._cap = None
        self._current_value = 0.0
        self._window_size = max(1, int(window_size))
        self._samples = deque(maxlen=self._window_size)
        self._last_warn_ts = 0.0
        self._read_failures = 0
        self._reinit_attempts = 0

    def start(self):
        if self._running:
            return
        if Picamera2 is None:
            print("CAMERA ERROR: Picamera2 is not available. Install picamera2 on Raspberry Pi OS.")
            return
        # Initialize Picamera2
        try:
            self._picam = Picamera2(0)
            # Configure preview with desired resolution and RGB888 format
            try:
                main_cfg = {"format": "RGB888"}
                if self.capture_size is not None:
                    main_cfg["size"] = self.capture_size
                config = self._picam.create_preview_configuration(main=main_cfg)
                self._picam.configure(config)
            except Exception:
                # If configuration fails, proceed with defaults
                pass
            # try:
            #     self._picam.set_controls({
            #         "AwbEnable": True,
            #         "ColourGains": (1.0, 1.0)
            #     })
            # except Exception:
            #     pass
            self._picam.start()

            # Apply exposure controls if requested
            try:
                controls = {}
                # If user provided exposure time but didn't specify AE, disable AE to honor manual exposure
                if self.exposure_time_us is not None and self.ae_enable is None:
                    controls["AeEnable"] = False
                if self.ae_enable is not None:
                    controls["AeEnable"] = bool(self.ae_enable)
                if self.exposure_time_us is not None:
                    controls["ExposureTime"] = int(self.exposure_time_us)
                if controls:
                    self._picam.set_controls(controls)
            except Exception:
                pass

        except Exception as e:
            print("CAMERA ERROR: Failed to initialize Picamera2:", e)
            self._picam = None
            return
        self._running = True
        self._thread = threading.Thread(target=self._camera_loop_picam, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        # Stop Picamera2 if running
        if getattr(self, "_picam", None):
            try:
                self._picam.stop()
            except Exception:
                pass
            self._picam = None

    def _camera_loop_picam(self):
        try:
            while self._running and getattr(self, "_picam", None) is not None:
                try:
                    frame = self._picam.capture_array()
                except Exception:
                    frame = None
                if frame is None:
                    self._read_failures += 1
                    now = time.time()
                    if now - self._last_warn_ts > 2.0:
                        print("CAMERA WARNING: Unable to read frame from Picamera2")
                        self._last_warn_ts = now
                    time.sleep(0.02)
                    continue

                # Convert to BGR for OpenCV operations and saving
                # try:
                #     frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                # except Exception:
                #     frame_bgr = frame

                cv2.imwrite('cam.jpg', frame)

                # Red-dominance mask tuned to avoid segmenting white:
                # - Strong red: R >= 200
                # - Red margin: R - max(G,B) >= 50
                # - Suppress white: G < 200 and B < 200
                th = 50
                try:
                    b, g, r = cv2.split(frame)
                    # Debug: export red channel
                    try:
                        cv2.imwrite('cam_red.png', r)
                    except Exception:
                        pass
                    red_high = r >= th
                    margin = (r.astype('int16') - cv2.max(g, b)) >= 50
                    not_white = (g < th) & (b < th)
                    raw_mask = (red_high & margin & not_white).astype('uint8') * 255
                    raw_mask = cv2.morphologyEx(raw_mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
                except Exception:
                    # Fallback: no mask
                    raw_mask = None

                # Keep only the largest connected red blob
                if raw_mask is not None:
                    try:
                        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(raw_mask, connectivity=8)
                        if num_labels > 1:
                            # label 0 is background; find largest area among labels 1..n-1
                            areas = stats[1:, cv2.CC_STAT_AREA]
                            largest_idx = int(1 + areas.argmax())
                            mask = (labels == largest_idx).astype('uint8') * 255
                        else:
                            mask = raw_mask
                    except Exception:
                        mask = raw_mask
                else:
                    mask = None

                try:
                    if mask is not None:
                        cv2.imwrite('cam_mask.png', mask)
                        overlay = frame_bgr.copy()
                        red_layer = overlay.copy()
                        red_layer[:, :] = (0, 0, 255)
                        alpha = 0.4
                        overlay = cv2.addWeighted(red_layer, alpha, overlay, 1 - alpha, 0, mask=mask)
                        cv2.imwrite('cam_overlay.jpg', overlay)
                except Exception:
                    pass

                value = int(cv2.countNonZero(mask)) if mask is not None else 0

                with self._lock:
                    self._current_value = value
                    self._samples.append(value)

                time.sleep(0.01)
        except Exception as e:
            print(f"CAMERA SENSOR ERROR: {e}")
            self._running = False

    # Old OpenCV fallback removed per requirement to use Picamera2
