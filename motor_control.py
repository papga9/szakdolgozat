import RPi.GPIO as GPIO
import time

class StepperMotor:
    def __init__(self, step_pin=23, dir_pin=24, enable_pin=25, full_steps=200, microsteps=16):
        self.step_pin = step_pin
        self.dir_pin = dir_pin
        self.enable_pin = enable_pin
        
        self.steps_per_rev = full_steps * microsteps
        
        # GPIO Setup
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.step_pin, GPIO.OUT)
        GPIO.setup(self.dir_pin, GPIO.OUT)
        GPIO.setup(self.enable_pin, GPIO.OUT)
        
        self.disable()

    def enable(self):
        GPIO.output(self.enable_pin, GPIO.LOW)

    def disable(self):
        GPIO.output(self.enable_pin, GPIO.HIGH)

    def cleanup(self):
        self.disable()
        GPIO.cleanup()

    def move(self, dist_mm, lead_mm, speed_rps=0.5, progress_callback=None):
        """
        dist_mm: távolság mm-ben
        lead_mm: menetes szár emelkedése (mm/fordulat)
        speed_rps: sebesség (fordulat/mp)
        progress_callback: egy függvény, amit időnként meghív mozgás közben (pl. kijelzéshez)
        """
        if lead_mm <= 0: return

        rotations = dist_mm / lead_mm
        total_steps = int(abs(rotations) * self.steps_per_rev)
        direction = 1 if rotations > 0 else -1
        
        # Irány beállítása
        GPIO.output(self.dir_pin, GPIO.HIGH if direction == 1 else GPIO.LOW)

        # Késleltetés számítása
        delay = (1.0 / (self.steps_per_rev * speed_rps)) / 2.0
        if delay < 0.000002: delay = 0.000002

        print(f"Mozgás indítása: {dist_mm} mm ({total_steps} lépés)")
        
        self.enable()
        time.sleep(0.05)

        mm_per_step = lead_mm / self.steps_per_rev
        current_pos = 0.0
        last_callback_time = time.time()

        try:
            for i in range(total_steps):
                GPIO.output(self.step_pin, GPIO.HIGH)
                time.sleep(delay)
                GPIO.output(self.step_pin, GPIO.LOW)
                time.sleep(delay)

                current_pos += (mm_per_step * direction)

                if progress_callback and (time.time() - last_callback_time > 0.1):
                    progress_callback(current_pos)
                    last_callback_time = time.time()

        except KeyboardInterrupt:
            print("\nMotor mozgás megszakítva!")
            raise

        finally:
            self.disable()