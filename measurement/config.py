from dataclasses import dataclass

# 1. Definiáljuk a rész-struktúrákat (mint C++ struct-ok)
@dataclass(frozen=True)
class MotorSettings:
    step_pin: int
    dir_pin: int
    enable_pin: int
    default_speed: float
    max_steps: int

@dataclass(frozen=True)
class EndstopSettings:
    pin: int
    pin: int
    is_normally_open: bool

# 2. Definiáljuk a fő konfigurációs osztályt, ami összefogja a többit
@dataclass(frozen=True)
class SystemConfig:
    motor: MotorSettings
    endstop: EndstopSettings
    debug_mode: bool = True  # Alapértelmezett érték

# 3. Példányosítjuk a konfigurációt a konkrét adatokkal
# Ez az egyetlen objektum, amit a többi fájl importálni fog
cfg = SystemConfig(
    motor=MotorSettings(
        step_pin=23,
        dir_pin=24,
        enable_pin=25,
        default_speed=10.5,
        max_steps=20000
    ),
    endstop=EndstopSettings(
        pin=17,
        is_normally_open=True
    ),
    # A debug_mode-ot nem kötelező megadni, mert van default értéke,
    # de felülírható:
    debug_mode=True
)