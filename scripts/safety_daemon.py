#!/usr/bin/env python3
import RPi.GPIO as GPIO
import time
import os
import signal
import sys
import subprocess


PIN = 22  # BCM numbering for GPIO22


def _trigger_shutdown():
    try:
        subprocess.Popen(["sudo", "shutdown", "now"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        os.system("sudo shutdown now")


def main():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    triggered = {"value": False}

    def on_button_press(channel: int):
        if triggered["value"]:
            return
        # Debounce and confirm the button is still pressed (active low)
        time.sleep(0.05)
        if GPIO.input(PIN) == GPIO.LOW:
            triggered["value"] = True
            _trigger_shutdown()

    GPIO.add_event_detect(PIN, GPIO.FALLING, callback=on_button_press, bouncetime=200)

    def _cleanup(signum=None, frame=None):
        try:
            GPIO.remove_event_detect(PIN)
        except Exception:
            pass
        GPIO.cleanup()
        if signum is not None:
            sys.exit(0)

    # Handle termination signals for clean GPIO release
    signal.signal(signal.SIGINT, _cleanup)
    signal.signal(signal.SIGTERM, _cleanup)

    try:
        while True:
            signal.pause()
    finally:
        _cleanup()


if __name__ == "__main__":
    main()
