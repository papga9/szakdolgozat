import RPi.GPIO as GPIO


class Endstop:
    def __init__(self, pin, pressed_state=0):
        """
        Egyetlen végállás kapcsoló kezelése.
        pin: A GPIO pin száma (BCM módban).
        """
        self.pin = pin
        self.pressed_state = pressed_state

        # GPIO mód ellenőrzése
        if GPIO.getmode() is None:
            GPIO.setmode(GPIO.BCM)

        # Bemenet beállítása (Pull-up ellenállással)
        # Alapból HIGH (3.3V), benyomva LOW (0V) lesz.
        GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    def is_pressed(self):
        """
        Igazat (True) ad vissza, ha a gomb be van nyomva (tehát a jel LOW/0V).
        """
        # Mivel Pull-up van: 0 = Benyomva, 1 = Felengedve
        return GPIO.input(self.pin) == self.pressed_state

    def is_open(self):
        """
        Igazat (True) ad vissza, ha a gomb nincs benyomva (szabad).
        """
        return GPIO.input(self.pin) != self.pressed_state

    def state_str(self):
        """
        Visszaad egy olvasható szöveget debuggoláshoz.
        """
        return "ZÁRVA (Actív)" if self.is_pressed() else "NYITVA (Inaktív)"

    def cleanup(self):
        """Csak ennek az egy kapcsolónak a pinjét takarítja ki."""
        GPIO.cleanup(self.pin)
