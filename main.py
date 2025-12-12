import argparse
import time
import os
import requests
from dataclasses import dataclass
from typing import Tuple

from measurement.motor_control import StepperMotor
from measurement.endstop import Endstop
from measurement.sensor_read import VoltageSensor, CameraSensor
from measurement.config import cfg


class ApiClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = base_url or os.environ.get("API_BASE_URL", "http://raspberrypi.local:5000")
        self.api_key = api_key or os.environ.get("API_UPDATE_KEY", "dev-secret")
        self.enabled = bool(self.base_url)

    def update(self, payload: dict, timeout: float = 1.5) -> None:
        if not self.enabled:
            return
        try:
            requests.post(f"{self.base_url}/api/update", json=payload, headers={"X-API-Key": self.api_key}, timeout=timeout)
        except Exception:
            pass

    def get_status(self, timeout: float = 1.5) -> dict | None:
        if not self.enabled:
            return None
        try:
            r = requests.get(f"{self.base_url}/api/status", timeout=timeout)
            if r.status_code == 200:
                return r.json()
        except Exception:
            return None
        return None


@dataclass
class MeasurementParams:
    lead_mm: float = 8.0
    laser_offset_mm: float = -32.0
    sensor_offset_mm: float = 135.0
    max_travel_mm: float = 280.0
    coarse_step_mm: float = 3.0
    fine_step_mm: float = 0.2
    max_swings: int = 5
    hysteresis: float = 0.05
    steps_threshold: int = 5
    sensor: str = "voltage"

    @classmethod
    def from_args(cls) -> "MeasurementParams":
        p = argparse.ArgumentParser(description="Lens focal length measurement")
        p.add_argument("--lead-mm", type=float, default=8.0, help="Lead of screw (mm per rev)")
        p.add_argument("--laser-offset-mm", type=float, default=0.0)
        p.add_argument("--sensor-offset-mm", type=float, default=150.0)
        p.add_argument("--max-travel-mm", type=float, default=100.0)
        p.add_argument("--coarse-step-mm", type=float, default=3.0)
        p.add_argument("--fine-step-mm", type=float, default=0.2)
        p.add_argument("--max-swings", type=int, default=5)
        p.add_argument("--hysteresis", type=float, default=0.02, help="Voltage drop to trigger reversal")
        p.add_argument("--steps-threshold", type=int, default=5, help="Number of steps without improvement to stop")
        p.add_argument(
            "--sensor",
            choices=["voltage", "camera"],
            default="voltage",
            help="Select the sensor backend: 'voltage' or 'camera'",
        )

        a = p.parse_args()

        return cls(
            lead_mm=a.lead_mm,
            laser_offset_mm=a.laser_offset_mm,
            sensor_offset_mm=a.sensor_offset_mm,
            max_travel_mm=a.max_travel_mm,
            coarse_step_mm=a.coarse_step_mm,
            fine_step_mm=a.fine_step_mm,
            max_swings=a.max_swings,
            hysteresis=a.hysteresis,
            steps_threshold=a.steps_threshold,
            sensor=a.sensor,
        )


class MeasurementRunner:
    def __init__(self, params: MeasurementParams, api: ApiClient):
        self.params = params
        self.api = api
        self.motor = StepperMotor(step_pin=cfg.motor.step_pin, dir_pin=cfg.motor.dir_pin, enable_pin=cfg.motor.enable_pin)
        self.endstop = Endstop(pin=cfg.endstop.pin)
        self.homestop = Endstop(pin=cfg.homestop.pin)
        if self.params.sensor == "camera":
            self.sensor = CameraSensor()
        else:
            self.sensor = VoltageSensor()

    def start(self):
        self.sensor.start()

    def stop(self):
        self.sensor.stop()
        self.motor.cleanup()

    def check_stop(self) -> bool:
        """Return True if a stop command is requested by the web UI."""
        state = self.api.get_status()
        if not state:
            return False
        cmd = state.get("desired_cmd")
        return cmd == "stop"

    def home(self) -> None:
        self.api.update({"is_homing": True, "desired_cmd": None})
        print("Homing axis...")
        print("Waiting for homing button press...")
        self.motor.set_direction(-1)
        last_check = time.time()
        while not self.homestop.is_pressed():
            # periodic stop check
            if time.time() - last_check > 0.5:
                if self.check_stop():
                    print("Stop command received during homing; aborting.")
                    return
                last_check = time.time()
            time.sleep(0.05)
            self.motor.move(dist_mm=1.0, lead_mm=self.params.lead_mm, speed_rps=1.0)
        self.api.update({"current_pos_mm": 0.0, "is_homing": False})

    def search_peak(self) -> Tuple[float, float]:
        print("Searching peak...")
        best_val = -1.0
        best_pos_mm = 0.0
        pos_mm = 0.0
        direction = 1
        swings = 0

        step = self.params.coarse_step_mm
        number_of_steps_wrong_direction = 0
        lastupdate = time.time()

        while swings < self.params.max_swings and pos_mm < self.params.max_travel_mm:
            if pos_mm + direction * step > self.params.max_travel_mm or pos_mm + direction * step <= 0:
                break

            self.motor.move(dist_mm=step, lead_mm=self.params.lead_mm, speed_rps=2.0)
            if self.endstop.is_pressed():
                print("Endstop pressed during scan; stopping movement.")
                self.api.update({"is_running": False})
                break
            pos_mm += direction * step
            time.sleep(0.05)
            # check stop command from web
            if time.time() - lastupdate > 0.5:
                if self.check_stop():
                    print("Stop command received; aborting.")
                    break
                self.api.update({
                    "current_pos_mm": pos_mm,
                    "current_voltage": val,
                    "best_pos_mm": best_pos_mm,
                    "best_voltage": best_val,
                    "is_running": True
                })
                lastupdate = time.time()
            val = self.sensor.get_value()
            if val > best_val:
                best_val = val
                best_pos_mm = pos_mm
            if best_val - val > self.params.hysteresis:
                number_of_steps_wrong_direction += 1

            if number_of_steps_wrong_direction >= self.params.steps_threshold:
                number_of_steps_wrong_direction = 0
                direction *= -1
                swings += 1
                self.motor.set_direction(direction)
                step = max(self.params.fine_step_mm, step / 2.0)
                print(f"Reversing direction. New step size: {step:.3f} mm. Swings: {swings}/{self.params.max_swings}")

        return best_pos_mm, best_val

    def compute_focal_length(self, laser_offset_mm: float, sensor_offset_mm: float, lens_pos_mm: float) -> float:
        laser_to_lense_mm = lens_pos_mm - laser_offset_mm
        sensor_to_lense_mm = self.params.max_travel_mm - lens_pos_mm + sensor_offset_mm

        return (laser_to_lense_mm*sensor_to_lense_mm)/(laser_to_lense_mm+sensor_to_lense_mm)


class App:
    def run(self) -> None:
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("--standalone", action="store_true", help="Run without web server integration")
        parser.add_argument("--no-home", action="store_true", help="Skip homing step in standalone mode")
        # Parse known to avoid conflicting with MeasurementParams
        known, _ = parser.parse_known_args()
        params = MeasurementParams.from_args()
        print("\n=== LASER SAFETY WARNING ===")
        print("This system may emit laser light. Protect eyes and skin.")
        print("- Always use appropriate laser safety goggles.")
        print("- Keep the beam enclosed and avoid reflective surfaces.")
        print("- Ensure bystanders are informed and protected.")
        print("Proceed only if the area is safe.\n")
        api = ApiClient(base_url=None if known.standalone else os.environ.get("API_BASE_URL", "http://raspberrypi.local:5000"))
        runner = MeasurementRunner(params, api)

        runner.start()
        try:
            if known.standalone:
                if not known.no_home:
                    runner.home()
                best_pos_mm, best_val = runner.search_peak()
                focal = runner.compute_focal_length(params.laser_offset_mm, params.sensor_offset_mm, best_pos_mm)
                print(f"Peak at {best_pos_mm:.2f} mm, intensity {best_val:.3f} V")
                print(f"Estimated focal length: {focal:.2f} mm")
            else:
                while True:
                    state = api.get_status()
                    if not state:
                        time.sleep(0.5)
                        continue
                    cmd = state.get("desired_cmd")

                    if cmd == "home":
                        runner.home()
                    if cmd == "start":
                        runner.home()
                        api.update({"is_running": True, "desired_cmd": None})
                        best_pos_mm, best_val = runner.search_peak()
                        focal = runner.compute_focal_length(params.laser_offset_mm, params.sensor_offset_mm, best_pos_mm)
                        print(f"Peak at {best_pos_mm:.2f} mm, intensity {best_val:.3f} V")
                        print(f"Estimated focal length: {focal:.2f} mm")
                        api.update({
                            "best_pos_mm": best_pos_mm,
                            "best_voltage": best_val,
                            "focal_length": focal
                        })

                    if cmd == "stop":
                        api.update({"is_running": False, "is_homing": False, "desired_cmd": None})

                    time.sleep(0.5)
        finally:
            runner.stop()


if __name__ == "__main__":
    try:
        # Re-create parser to display warning along with help
        parser = argparse.ArgumentParser(
            description=(
                "Lens focal length measurement.\n\n"
                "SAFETY: This device may operate a laser. Use certified eye protection,\n"
                "avoid direct/indirect exposure, and secure reflective paths."
            )
        )
    except Exception:
        pass
    App().run()
