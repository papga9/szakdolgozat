from measurement.camera_sensor import CameraSensor
import time

camera = CameraSensor()
camera.start()

while True:
    print(f"{camera.get_value()}")

    time.sleep(1)
