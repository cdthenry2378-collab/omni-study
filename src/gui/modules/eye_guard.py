"""Optional OpenCV attention monitor; disabled unless explicitly enabled."""
from PyQt6.QtCore import QThread, pyqtSignal
import time

class EyeGuardWorker(QThread):
    attention_drop = pyqtSignal(dict)
    status = pyqtSignal(str)

    def __init__(self, camera_index=0, sample_seconds=1.0, parent=None):
        super().__init__(parent)
        self.camera_index = camera_index
        self.sample_seconds = max(.2, sample_seconds)
        self._running = True

    def stop(self):
        self._running = False
        self.wait(1500)

    def run(self):
        try:
            import cv2
        except ImportError:
            self.status.emit("Eye Guard unavailable: OpenCV is not installed.")
            return
        capture = cv2.VideoCapture(self.camera_index)
        if not capture.isOpened():
            self.status.emit("Eye Guard unavailable: webcam could not be opened.")
            return
        # Privacy: frames are processed in memory only; no images are saved or transmitted.
        # Haar face detection is a rough presence proxy, not medically valid gaze/blink analysis.
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        detector = cv2.CascadeClassifier(cascade_path)
        absent = 0
        try:
            while self._running:
                ok, frame = capture.read()
                if not ok:
                    self.status.emit("Eye Guard: camera frame unavailable.")
                    time.sleep(self.sample_seconds); continue
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = detector.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(50,50))
                absent = absent + 1 if len(faces) == 0 else 0
                if absent >= 8:
                    self.attention_drop.emit({"reason": "face_not_detected", "suggestion": "Try a short break or explain the concept in simpler terms."})
                    absent = 0
                time.sleep(self.sample_seconds)
        finally:
            capture.release()
            self.status.emit("Eye Guard stopped.")
