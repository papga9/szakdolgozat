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
class KalmanConfig:
    process_noise: float
    measurement_noise: float
    estimation_error: float
    initial_value: float

@dataclass(frozen=True)
class SystemConfig:
    motor: MotorSettings
    endstop: EndstopSettings
    kalman: KalmanConfig
    debug_mode: bool = True

cfg = SystemConfig(
    motor=MotorSettings(23, 24, 25, 10.0, 2000),
    endstop=EndstopSettings(pin=16, is_normally_open=True),
    endstop=EndstopSettings(pin=18, is_normally_open=True),
    kalman=KalmanConfig(1e-5, 0.1, 1.0, 0.0)
)