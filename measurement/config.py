from dataclasses import dataclass


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
    is_normally_open: bool


@dataclass(frozen=True)
class SystemConfig:
    motor: MotorSettings
    endstop: EndstopSettings
    homestop: EndstopSettings
    debug_mode: bool = True


cfg = SystemConfig(
    motor=MotorSettings(6, 12, 5, 10.0, 2000),
    endstop=EndstopSettings(pin=14, is_normally_open=True),
    homestop=EndstopSettings(pin=15, is_normally_open=True),
)
