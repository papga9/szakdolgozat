import RPi.GPIO as GPIO
from config import EndstopSettings 

class Endstop:
    def __init__(self, settings: EndstopSettings):
        self.settings = settings
        self.pin = settings.pin

        if GPIO.getmode() is None:
            GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    def is_pressed(self) -> bool:
        state = GPIO.input(self.pin)
        
        if self.settings.is_normally_open:
            return state == 0
        else:
            return state == 1

    def is_open(self) -> bool:
        return not self.is_pressed()

    def cleanup(self):
        GPIO.cleanup(self.pin)