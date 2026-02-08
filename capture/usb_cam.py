import cv2
import time

def take_photo(device_index: int = 0, width: int = 1280, height: int = 720):
    cap = cv2.VideoCapture(device_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    # warm up buffer
    for _ in range(5):
        cap.read()

    time.sleep(0.15)  # let auto WB/exposure settle
    ok, frame = cap.read()

    cap.release()
    if not ok or frame is None:
        raise RuntimeError("Camera read failed")
    return frame
