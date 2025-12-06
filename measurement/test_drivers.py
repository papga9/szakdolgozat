import sys
import unittest
from unittest.mock import MagicMock, patch

# --- 1. GLOBÁLIS MOCK ELŐKÉSZÍTÉS ---
# Létrehozzuk a mock objektumokat, amiket figyelni fogunk
mock_gpio = MagicMock()
mock_smbus_cls = MagicMock()
mock_i2c_msg = MagicMock()

# Beállítjuk a konstansokat (hogy a számítások működjenek)
mock_gpio.BCM = 11
mock_gpio.OUT = 1
mock_gpio.IN = 0
mock_gpio.HIGH = 1
mock_gpio.LOW = 0
mock_gpio.PUD_UP = 22

# A rendszernek azt hazudjuk, hogy ezek a modulok léteznek
sys.modules["RPi"] = MagicMock()
sys.modules["RPi.GPIO"] = mock_gpio
sys.modules["smbus2"] = MagicMock()
sys.modules["smbus2"].SMBus = mock_smbus_cls
sys.modules["smbus2"].i2c_msg = mock_i2c_msg

# --- 2. MODULOK IMPORTÁLÁSA ---
try:
    import motor_control
    import endstop
    import sensor_read
except ImportError as e:
    print(f"KRITIKUS HIBA: Nem találhatók a fájlok: {e}")
    sys.exit(1)

# --- 3. FONTOS: MOCK INJEKTÁLÁS (A JAVÍTÁS LÉNYEGE) ---
# Itt biztosítjuk, hogy a te kódod PONTOSAN azt a mock-ot használja, amit mi figyelünk
motor_control.GPIO = mock_gpio
endstop.GPIO = mock_gpio
# A szenzor modulnál kicsit trükkösebb, mert ott az osztályokat használja
# De mivel sys.modules-ban ott van, elvileg jónak kell lennie. 
# Ha biztosra akarunk menni, a VoltageSensor initjében lévő SMBus-t is mockolhatjuk context managerrel.

class TestStepperMotor(unittest.TestCase):
    def setUp(self):
        # Minden teszt előtt nullázzuk a híváslistát
        mock_gpio.reset_mock()
        
        # Példányosítjuk az osztályt a tesztelt modulból
        self.motor = motor_control.StepperMotor(step_pin=23, dir_pin=24, enable_pin=25)

    def test_initialization(self):
        """GPIO setup hívások ellenőrzése"""
        # Ellenőrizzük, hogy a konstruktor beállította-e a módokat
        mock_gpio.setmode.assert_called_with(11) # 11 = BCM
        mock_gpio.setup.assert_any_call(23, 1)   # 1 = OUT
        mock_gpio.setup.assert_any_call(24, 1)
        mock_gpio.setup.assert_any_call(25, 1)

    @patch("time.sleep") # Kikapcsoljuk a várakozást
    def test_move_positive_direction(self, mock_sleep):
        """Előre mozgás (10mm)"""
        self.motor.move(dist_mm=10, lead_mm=2, speed_rps=10)
        
        # Irány pin (24) legyen HIGH (1)
        mock_gpio.output.assert_any_call(24, 1)
        # Enable pin (25) legyen LOW (0)
        mock_gpio.output.assert_any_call(25, 0)
        # Step pin (23) rángatása (elég, ha egyszer hívták)
        mock_gpio.output.assert_any_call(23, 1)

    @patch("time.sleep")
    def test_move_negative_direction(self, mock_sleep):
        """Hátra mozgás (-4mm)"""
        self.motor.move(dist_mm=-4, lead_mm=2)
        
        # Irány pin (24) legyen LOW (0)
        mock_gpio.output.assert_any_call(24, 0)


class TestEndstop(unittest.TestCase):
    def setUp(self):
        mock_gpio.reset_mock()
        self.endstop_obj = endstop.Endstop(pin=17)

    def test_setup(self):
        # Setup hívás ellenőrzése: pin 17, IN(0), PUD_UP(22)
        mock_gpio.setup.assert_called_with(17, 0, pull_up_down=22)

    def test_is_pressed(self):
        """Ha a GPIO bemenet 0, akkor a gomb be van nyomva"""
        mock_gpio.input.return_value = 0 # Szimuláljuk, hogy a hardver 0-t olvas
        
        self.assertTrue(self.endstop_obj.is_pressed())
        self.assertFalse(self.endstop_obj.is_open())
        
        # Ellenőrizzük, hogy tényleg meghívta-e az olvasást
        mock_gpio.input.assert_called_with(17)

    def test_is_open(self):
        """Ha a GPIO bemenet 1, akkor a gomb nyitva van"""
        mock_gpio.input.return_value = 1 # Szimuláljuk, hogy a hardver 1-et olvas
        
        self.assertFalse(self.endstop_obj.is_pressed())
        self.assertTrue(self.endstop_obj.is_open())


class TestVoltageSensor(unittest.TestCase):
    def setUp(self):
        self.sensor = sensor_read.VoltageSensor(res_bits=16, vref=2.048)

    def test_config_logic(self):
        # Csak a belső logikát teszteljük, hogy a biteket jól számolja-e
        self.assertEqual(self.sensor._rb_cfg, 0b10)

if __name__ == '__main__':
    unittest.main()