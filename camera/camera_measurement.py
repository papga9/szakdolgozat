import numpy as np
import cv2
import glob
import yaml
import os
import time

# --- FELHASZNÁLÓI KONFIGURÁCIÓ ---

# 1. A kamera és a hozzáadott lencse közötti távolság (mm-ben)
DISTANCE_LENS_CAM_MM = 20.0  

# 2. A szenzor pixelmérete (mm-ben). 
# Pi Camera v2 (Sony IMX219) pixelmérete: 1.12 µm = 0.00112 mm
SENSOR_PIXEL_SIZE_MM = 0.00112 

# 3. Sakktábla beállítások
CHESSBOARD_SIZE = (9, 6) # Belső sarkok száma (szélesség, magasság)
SQUARE_SIZE_MM = 20.0    # Négyzet mérete mm-ben

# --- Egyéb beállítások ---
OUTPUT_FILE = 'camera_matrix_pi.yaml'
CRITERIA = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

# --- KAMERA KEZELŐ OSZTÁLY (PiCamera2 vs OpenCV) ---
class CameraHandler:
    def __init__(self):
        self.use_picamera = False
        self.cap = None
        self.picam2 = None

        try:
            from picamera2 import Picamera2
            self.picam2 = Picamera2()
            
            # Pi Camera 2 konfig: 1640x1232 (Binning mód)
            config = self.picam2.create_configuration(main={"size": (1640, 1232), "format": "BGR888"})
            self.picam2.configure(config)
            self.picam2.start()
            
            self.use_picamera = True
            print(">> Picamera2 (Raspberry Pi Camera) sikeresen inicializálva.")
        except ImportError:
            print(">> Picamera2 nem található. Visszatérés a szabványos USB webkamerához (cv2).")
            self.cap = cv2.VideoCapture(0)
        except Exception as e:
            print(f">> Hiba a PiCamera indításakor: {e}. Visszatérés cv2-re.")
            if self.picam2:
                self.picam2.stop()
            self.cap = cv2.VideoCapture(0)

    def get_frame(self):
        """Visszaad egy képet (numpy array) BGR formátumban."""
        if self.use_picamera:
            # Picamera2 array lekérése (non-blocking, ha lehetne, de itt egyszerűsítünk)
            return self.picam2.capture_array()
        else:
            if not self.cap.isOpened():
                return None
            ret, frame = self.cap.read()
            if not ret:
                return None
            return frame

    def release(self):
        if self.use_picamera:
            if self.picam2:
                self.picam2.stop()
        else:
            if self.cap:
                self.cap.release()

# ---------------------------------------------------

def capture_images(phase_name):
    """
    Képeket készít a kamerával.
    """
    cam = CameraHandler()
    images = []
    
    print(f"\n--- {phase_name} FÁZIS: Képek készítése ---")
    print("Nyomj 'c'-t a kép készítéséhez.")
    print("Nyomj 'q'-t a befejezéshez.")

    count = 0
    while True:
        frame = cam.get_frame()
        if frame is None:
            print("Hiba: Nem érkezik kép a kamerából.")
            time.sleep(1)
            continue

        display_h = 600
        h, w = frame.shape[:2]
        ratio = display_h / h
        display_frame = cv2.resize(frame, (int(w * ratio), int(h * ratio)))

        cv2.putText(display_frame, f"Kepek: {count} | 'c': Foto | 'q': Kesz", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        cv2.imshow(f'Capture - {phase_name}', display_frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('c'):
            images.append(frame.copy())
            count += 1
            print(f"Kép rögzítve! ({count} db)")
            
            inverted = cv2.bitwise_not(display_frame)
            cv2.imshow(f'Capture - {phase_name}', inverted)
            cv2.waitKey(50)
            
        elif key == ord('q'):
            break

    cam.release()
    cv2.destroyAllWindows()
    return images

def calibrate_system(images, phase_name):
    """
    Végrehajtja a sakktáblás kalibrációt.
    """
    if len(images) == 0:
        print(f"Hiba: Nincs kép a {phase_name} fázishoz.")
        return None

    print(f"\nKalibráció futtatása ({phase_name})... Képek száma: {len(images)}")
    
    objp = np.zeros((CHESSBOARD_SIZE[0] * CHESSBOARD_SIZE[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:CHESSBOARD_SIZE[0], 0:CHESSBOARD_SIZE[1]].T.reshape(-1, 2)
    objp = objp * SQUARE_SIZE_MM

    objpoints = [] 
    imgpoints = [] 
    gray = None
    found_count = 0

    for i, img in enumerate(images):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        ret, corners = cv2.findChessboardCorners(gray, CHESSBOARD_SIZE, None)

        if ret:
            objpoints.append(objp)
            corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), CRITERIA)
            imgpoints.append(corners2)
            found_count += 1
            print(f"  [{i+1}/{len(images)}] Sakktábla OK")
        else:
            print(f"  [{i+1}/{len(images)}] Sakktábla NEM található")

    if found_count == 0:
        print(f"Hiba: Nem találtam sakktáblát egy képen sem a {phase_name} fázisban.")
        return None

    print("Kamera paraméterek számolása...")
    ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(objpoints, imgpoints, gray.shape[::-1], None, None)

    if ret:
        print(f"Sikeres kalibráció: {phase_name}")
        print(f"Fx: {mtx[0,0]:.2f}, Fy: {mtx[1,1]:.2f} (pixel)")
        return mtx
    else:
        print(f"Hiba: A kalibráció sikertelen ({phase_name}).")
        return None

def calculate_lens_focal_length(mtx_cam, mtx_sys, d_mm, pixel_size_mm):
    """
    Kiszámítja az ismeretlen lencse fókusztávolságát.
    """
    f_cam_pix = (mtx_cam[0, 0] + mtx_cam[1, 1]) / 2.0
    f_sys_pix = (mtx_sys[0, 0] + mtx_sys[1, 1]) / 2.0

    f_cam_mm = f_cam_pix * pixel_size_mm
    f_sys_mm = f_sys_pix * pixel_size_mm

    print("\n" + "="*40)
    print("EREDMÉNYEK A FIZIKAI RENDSZERRE (Pi Camera 2):")
    print(f"Kamera fókusz (f_cam): {f_cam_mm:.2f} mm")
    print(f"Rendszer fókusz (f_sys): {f_sys_mm:.2f} mm")
    print(f"Távolság (d): {d_mm} mm")

    if abs(f_cam_mm - f_sys_mm) < 0.001:
        print("Nincs érzékelhető változás a fókusztávolságban.")
        return

    try:
        # f_lens = (f_sys * (f_cam - d)) / (f_cam - f_sys)
        numerator = f_sys_mm * (f_cam_mm - d_mm)
        denominator = f_cam_mm - f_sys_mm
        
        f_lens_mm = numerator / denominator
        
        print("-" * 40)
        print(f"SZÁMÍTOTT LENCSE FÓKUSZTÁVOLSÁG: {f_lens_mm:.2f} mm")
        print("-" * 40)
        
        diopter = 1000 / f_lens_mm
        print(f"Lencse erőssége: {diopter:.2f} Dioptria")
        
    except ZeroDivisionError:
        print("Hiba: Osztás nullával.")

def main():
    print("=== PI CAMERA 2 LENCSE KALIBRÁTOR ===")
    
    mtx_cam = None

    # --- 1. LÉPÉS: ALAP KAMERA ---
    if os.path.exists(OUTPUT_FILE):
        print(f"\nTaláltam korábbi kalibrációs fájlt: {OUTPUT_FILE}")
        choice = input("Szeretnéd ezt használni a 'Meztelen' kamerához? (i/n): ").strip().lower()
        if choice == 'i':
            with open(OUTPUT_FILE, 'r') as f:
                data = yaml.safe_load(f)
                mtx_cam = np.array(data['camera_matrix'])
                print("Meglévő kamera mátrix betöltve.")
    
    if mtx_cam is None:
        print("\n--- 1. LÉPÉS: Kalibráljuk a PI KAMERÁT lencse NÉLKÜL ---")
        input("Győződj meg róla, hogy NINCS plusz lencse a kamera előtt. Nyomj Entert...")
        imgs_cam = capture_images("KAMERA_ONLY")
        mtx_cam = calibrate_system(imgs_cam, "KAMERA_ONLY")
        
        if mtx_cam is not None:
            data = {'camera_matrix': mtx_cam.tolist()}
            with open(OUTPUT_FILE, "w") as f:
                yaml.dump(data, f)
                print(f"Kamera mátrix elmentve ide: {OUTPUT_FILE}")

    if mtx_cam is None:
        print("Hiba: Nincs alap mátrix. Kilépés.")
        return

    # --- 2. LÉPÉS: TELJES RENDSZER ---
    print("\n--- 2. LÉPÉS: Kalibráljuk a rendszert LENCSÉVEL ---")
    print(f"Kérlek, helyezd az ismeretlen lencsét a Pi Camera elé {DISTANCE_LENS_CAM_MM} mm távolságra.")
    input("Ha készen állsz, nyomj Entert...")
    
    imgs_sys = capture_images("RENDSZER_LENS")
    mtx_sys = calibrate_system(imgs_sys, "RENDSZER_LENS")

    if mtx_sys is None:
        print("Hiba: Nincs rendszer mátrix. Kilépés.")
        return

    # --- 3. LÉPÉS: SZÁMÍTÁS ---
    calculate_lens_focal_length(mtx_cam, mtx_sys, DISTANCE_LENS_CAM_MM, SENSOR_PIXEL_SIZE_MM)

if __name__ == "__main__":
    main()