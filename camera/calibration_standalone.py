import numpy as np
import cv2
import glob
import yaml
import argparse
import os

# --- Argument Parsing ---
parser = argparse.ArgumentParser(description='Calibrate camera using checkerboard images.')
parser.add_argument('--width', type=int, required=True, help='Number of internal checkerboard corners (width). E.g., 9 for a 10x7 board.')
parser.add_argument('--height', type=int, required=True, help='Number of internal checkerboard corners (height). E.g., 6 for a 10x7 board.')
parser.add_argument('--square', type=float, required=True, help='Size of a single checkerboard square in mm.')
parser.add_argument('--path', type=str, default='calibration_images', help='Path to the directory containing calibration images.')
parser.add_argument('--ext', type=str, default='jpg', help='Image file extension (e.g., jpg, png).')
parser.add_argument('--no-preview', action='store_true', help='Disable the preview window that shows detected corners.')
args = parser.parse_args()

# --- Configuration ---
CHECKERBOARD = (args.width, args.height)
SQUARE_SIZE_MM = args.square
IMAGE_PATH = args.path
IMAGE_EXT = args.ext
OUTPUT_FILE = 'camera_matrix.yaml'

print("Starting calibration with the following settings:")
print(f"  Checkerboard Internal Corners: {CHECKERBOARD}")
print(f"  Square Size: {SQUARE_SIZE_MM} mm")
print(f"  Image Path: {IMAGE_PATH}")
print(f"  Image Extension: {IMAGE_EXT}")
print("="*30)

# --- Criteria for corner detection ---
criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

# --- Prepare 3D "object points" ---
objp = np.zeros((CHECKERBOARD[0] * CHECKERBOARD[1], 3), np.float32)
objp[:, :2] = np.mgrid[0:CHECKERBOARD[0], 0:CHECKERBOARD[1]].T.reshape(-1, 2)
objp = objp * SQUARE_SIZE_MM # Scale by square size

# --- Arrays to store object points and image points from all images ---
objpoints = [] # 3D points in real world space
imgpoints = [] # 2D points in image plane

# --- Find images ---
images = glob.glob(os.path.join(IMAGE_PATH, f'*.{IMAGE_EXT}'))

if not images:
    print(f"Error: No images found at {IMAGE_PATH} with extension {IMAGE_EXT}")
    print("Please run the capture_images.py script first.")
    exit()

print(f"Found {len(images)} images to process...")
found_corners = 0
gray = None # To store image shape

# --- Process each image ---
for fname in images:
    img = cv2.imread(fname)
    if img is None:
        print(f"Warning: Could not read image {fname}. Skipping.")
        continue

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Find the chess board corners
    ret, corners = cv2.findChessboardCorners(gray, CHECKERBOARD, None)

    # If found, add object points, image points (after refining them)
    if ret == True:
        found_corners += 1
        print(f"Found corners in: {fname}")
        objpoints.append(objp)

        # Refine corner locations
        corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
        imgpoints.append(corners2)

        # Draw and display the corners
        if not args.no_preview:
            cv2.drawChessboardCorners(img, CHECKERBOARD, corners2, ret)
            
            # Scale image for display if it's too large
            h, w = img.shape[:2]
            max_disp_h = 800
            if h > max_disp_h:
                scale = max_disp_h / h
                img_display = cv2.resize(img, (int(w * scale), int(h * scale)))
            else:
                img_display = img
                
            cv2.imshow('Found Corners', img_display)
            cv2.waitKey(500) # Show for 0.5 seconds
    else:
        print(f"Could not find corners in: {fname}")

if not args.no_preview:
    cv2.destroyAllWindows()

if found_corners == 0:
    print("\nError: Could not find corners in ANY image.")
    print("Check your --width and --height arguments or retake your pictures.")
    exit()

if gray is None:
    print("Error: No valid images were processed.")
    exit()
    
print(f"\nSuccessfully found corners in {found_corners} out of {len(images)} images.")
print("Running calibration...")

# --- Perform Calibration ---
ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(objpoints, imgpoints, gray.shape[::-1], None, None)

if not ret:
    print("Error: Calibration failed!")
    exit()

print("Calibration successful!")

# --- Save the calibration data ---
data = {
    'camera_matrix': np.asarray(mtx).tolist(),
    'dist_coeff': np.asarray(dist).tolist()
}

with open(OUTPUT_FILE, "w") as f:
    yaml.dump(data, f)

print(f"Calibration data saved to: {OUTPUT_FILE}")

# --- Optional: Print Reprojection Error ---
mean_error = 0
for i in range(len(objpoints)):
    imgpoints2, _ = cv2.projectPoints(objpoints[i], rvecs[i], tvecs[i], mtx, dist)
    error = cv2.norm(imgpoints[i], imgpoints2, cv2.NORM_L2) / len(imgpoints2)
    mean_error += error

print(f"Total Reprojection Error: {mean_error / len(objpoints)}")
print("(A low error, e.g., < 0.5, is good)")