# core/motion.py
import cv2
import numpy as np

class ChangeDetector:
    def __init__(self, roi=None, blur=7):
        self.roi = roi  # (x, y, w, h) or None
        self.blur = blur
        self._prev = None

    def _crop(self, frame):
        if not self.roi:
            return frame
        x, y, w, h = self.roi
        return frame[y:y+h, x:x+w]

    def score(self, frame) -> float:
        img = self._crop(frame)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        if self.blur and self.blur > 1:
            gray = cv2.GaussianBlur(gray, (self.blur, self.blur), 0)

        if self._prev is None:
            self._prev = gray
            return 0.0

        diff = cv2.absdiff(self._prev, gray)
        self._prev = gray

        # normalize 0..1
        return float(np.mean(diff) / 255.0)
