import time
import threading
from smbus2 import SMBus, i2c_msg
from collections import deque

from .sensor_base import SensorBase


class VoltageSensor(SensorBase):
    def __init__(self, i2c_addr=0x68, channel=0, res_bits=12, vref=2.048, board_scale=(5.06/2.048), window_size: int = 50):
        SensorBase.__init__(self)
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
