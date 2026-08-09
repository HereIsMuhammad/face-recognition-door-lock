"""
add_face.py

Helper script to register a new authorized face using the webcam.

Usage:
    python add_face.py <person_name>

Example:
    python add_face.py Ahmed

Controls:
    SPACE - capture and save the current frame
    ESC   - cancel without saving
"""

import os
import sys

import cv2
import yaml

KNOWN_FACES_DIR = "known_faces"
ENCODINGS_CACHE = "encodings.pkl"
CONFIG_PATH = "config.yaml"


def get_camera_source():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            config = yaml.safe_load(f)
        return config.get("camera_source", 0)
    return 0


def main():
    if len(sys.argv) < 2:
        print("Usage: python add_face.py <person_name>")
        print("Example: python add_face.py Ahmed")
        return

    name = sys.argv[1]
    os.makedirs(KNOWN_FACES_DIR, exist_ok=True)

    camera_source = get_camera_source()
    video = cv2.VideoCapture(camera_source)
    if not video.isOpened():
        print(f"Error: could not open camera source '{camera_source}'.")
        return

    print("Look at the camera.")
    print("Press SPACE to capture, ESC to cancel.")

    saved = False
    while True:
        ret, frame = video.read()
        if not ret:
            print("Failed to grab frame.")
            break

        cv2.imshow("Add Face - SPACE to capture, ESC to cancel", frame)
        key = cv2.waitKey(1) & 0xFF

        if key == 27:  # ESC
            print("Cancelled, no photo saved.")
            break
        elif key == 32:  # SPACE
            filepath = os.path.join(KNOWN_FACES_DIR, f"{name}.jpg")
            cv2.imwrite(filepath, frame)
            print(f"Saved: {filepath}")
            saved = True
            break

    video.release()
    cv2.destroyAllWindows()

    if saved and os.path.exists(ENCODINGS_CACHE):
        os.remove(ENCODINGS_CACHE)
        print("Face cache cleared — new face will be picked up on next run.")


if __name__ == "__main__":
    main()
