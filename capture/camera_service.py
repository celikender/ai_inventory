# capture/camera_service.py
import cv2
import os
import threading
import time

from dotenv import load_dotenv

load_dotenv()


class CameraService:
    """
    Keeps a single cv2.VideoCapture open and continuously updates the latest frame.
    get_frame() returns a copy of the newest frame (or None if stale/unavailable).
    """

    def __init__(self, src: int = 0, width: int = 1280, height: int = 720, read_sleep_s: float = 0.02):
        self.src = src
        self.width = width
        self.height = height
        self.read_sleep_s = read_sleep_s

        self.cap: cv2.VideoCapture | None = None
        self.lock = threading.Lock()
        self.current_frame = None
        self.last_frame_ts = 0.0

        self.running = False
        self.thread: threading.Thread | None = None

    def start(self):
        if self.running:
            return

        cap = cv2.VideoCapture(self.src)
        if not cap.isOpened():
            cap.release()
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

        # warm up exposure/WB
        for _ in range(10):
            cap.read()
            time.sleep(0.02)

        self.cap = cap
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
        self.cap = None
        self.thread = None

    def _loop(self):
        while self.running and self.cap:
            ok, frame = self.cap.read()
            if ok and frame is not None:
                with self.lock:
                    self.current_frame = frame
                    self.last_frame_ts = time.time()
            time.sleep(self.read_sleep_s)

    def get_frame(self, max_age_s: float = 1.0):
        with self.lock:
            if self.current_frame is None:
                return None
            if (time.time() - self.last_frame_ts) > max_age_s:
                return None
            return self.current_frame.copy()


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


# Singleton configured through environment variables for Raspberry Pi or laptop use.
cam_service = CameraService(
    src=_env_int("CAMERA_DEVICE_INDEX", 0),
    width=_env_int("CAMERA_WIDTH", 1280),
    height=_env_int("CAMERA_HEIGHT", 720),
)
