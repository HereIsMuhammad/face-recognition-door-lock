"""
face_door_lock.py

Main entry point for the Face Recognition Door Lock system.

- Reads settings from config.yaml
- Loads known faces from the known_faces/ folder
- Opens the camera and continuously checks incoming faces
- If a face matches a known face -> triggers the configured lock hardware
- If it doesn't match -> access denied (logged/printed)

Run:
    python face_door_lock.py

Press 'q' in the video window to quit.
"""

import os
import pickle
import time

import cv2
import face_recognition
import numpy as np
import yaml

from lock_controller import LockController

CONFIG_PATH = "config.yaml"
KNOWN_FACES_DIR = "known_faces"
ENCODINGS_CACHE = "encodings.pkl"


def load_config():
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def load_known_faces():
    """
    Loads known faces from known_faces/ and returns (encodings, names).
    Caches encodings in encodings.pkl so we don't re-process images every run.
    Cache is automatically invalidated if any file in known_faces/ is newer
    than the cache, or if a new photo is added.
    """
    os.makedirs(KNOWN_FACES_DIR, exist_ok=True)
    image_files = [
        f for f in os.listdir(KNOWN_FACES_DIR)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ]

    if os.path.exists(ENCODINGS_CACHE) and image_files:
        cache_time = os.path.getmtime(ENCODINGS_CACHE)
        newest_image_time = max(
            os.path.getmtime(os.path.join(KNOWN_FACES_DIR, f)) for f in image_files
        )
        if cache_time > newest_image_time:
            try:
                with open(ENCODINGS_CACHE, "rb") as f:
                    data = pickle.load(f)
                return data["encodings"], data["names"]
            except (pickle.UnpicklingError, EOFError, KeyError, OSError):
                print("Warning: encodings cache is corrupted, rebuilding it.")

    encodings = []
    names = []
    for filename in image_files:
        path = os.path.join(KNOWN_FACES_DIR, filename)
        # Load via OpenCV and force 8-bit RGB, contiguous array.
        # (Loading via face_recognition.load_image_file can sometimes produce
        # an image format that dlib's detector rejects with:
        # "Unsupported image type, must be 8bit gray or RGB image.")
        image_bgr = cv2.imread(path)
        if image_bgr is None:
            print(f"Warning: could not read '{filename}', skipping.")
            continue
        image = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        image = np.ascontiguousarray(image, dtype=np.uint8)
        face_encs = face_recognition.face_encodings(image)
        if face_encs:
            encodings.append(face_encs[0])
            names.append(os.path.splitext(filename)[0])
        else:
            print(f"Warning: no face found in '{filename}', skipping.")

    with open(ENCODINGS_CACHE, "wb") as f:
        pickle.dump({"encodings": encodings, "names": names}, f)

    return encodings, names


def main():
    config = load_config()
    tolerance = config.get("match_tolerance", 0.5)
    camera_source = config.get("camera_source", 0)
    unlock_duration = config.get("unlock_duration_seconds", 5)
    cooldown = config.get("cooldown_seconds", 10)

    known_encodings, known_names = load_known_faces()
    if not known_encodings:
        print(
            "No known faces found.\n"
            "Add at least one photo first, e.g.:\n"
            "    python add_face.py YourName\n"
        )
        return

    print(f"Loaded {len(known_names)} known face(s): {', '.join(known_names)}")

    lock = LockController(config)
    video = cv2.VideoCapture(camera_source)
    if not video.isOpened():
        print(f"Error: could not open camera source '{camera_source}'.")
        return

    print("Door lock system running. Press 'q' in the video window to quit.")
    last_unlock_time = 0
    last_deny_time = 0
    deny_message_interval = 2  # seconds between repeated "Access Denied" logs

    try:
        while True:
            ret, frame = video.read()
            if not ret:
                print("Failed to grab frame from camera.")
                break

            # Downscale for faster processing
            small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
            rgb_small = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
            rgb_small = np.ascontiguousarray(rgb_small, dtype=np.uint8)

            face_locations = face_recognition.face_locations(rgb_small)
            face_encodings = face_recognition.face_encodings(rgb_small, face_locations)

            access_granted = False
            matched_name = None

            for face_encoding in face_encodings:
                distances = face_recognition.face_distance(known_encodings, face_encoding)
                if len(distances) > 0:
                    best_idx = np.argmin(distances)
                    if distances[best_idx] <= tolerance:
                        access_granted = True
                        matched_name = known_names[best_idx]
                        break

            # Draw boxes for visual feedback
            for (top, right, bottom, left) in face_locations:
                top, right, bottom, left = top * 4, right * 4, bottom * 4, left * 4
                color = (0, 255, 0) if access_granted else (0, 0, 255)
                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)

            if access_granted:
                status_text = f"Access Granted: {matched_name}"
                text_color = (0, 255, 0)
            elif face_locations:
                status_text = "Access Denied"
                text_color = (0, 0, 255)
            else:
                status_text = "No face detected"
                text_color = (200, 200, 200)

            cv2.putText(frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                        0.8, text_color, 2)
            cv2.imshow("Face Recognition Door Lock", frame)

            now = time.time()
            if access_granted and (now - last_unlock_time) > cooldown:
                print(f"Access Granted: {matched_name}")
                lock.unlock(duration=unlock_duration)
                last_unlock_time = now
            elif face_locations and not access_granted and (now - last_deny_time) > deny_message_interval:
                lock.deny()
                last_deny_time = now

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        video.release()
        cv2.destroyAllWindows()
        lock.cleanup()


if __name__ == "__main__":
    main()