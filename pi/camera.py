"""C920 capture for the leaf pipeline (runs on the Pi; OpenCV backend).

The C920 auto-exposes over its first few frames, so capture() always grabs
and discards a short warmup burst before keeping one. grabber is injectable
so tests never need hardware.
"""

from __future__ import annotations

import time
from pathlib import Path


class Camera:
    def __init__(self, device: int = 0, warmup_frames: int = 6, grabber=None):
        self.device = device
        self.warmup_frames = warmup_frames
        self._grabber = grabber

    def _grab(self):
        if self._grabber is not None:
            return self._grabber()
        import cv2  # lazy: hardware/Pi only
        if not hasattr(self, "_cap"):
            self._cap = cv2.VideoCapture(self.device)
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        ok, frame = self._cap.read()
        if not ok:
            raise RuntimeError(f"camera {self.device} returned no frame")
        return frame

    def capture(self, path: str | Path) -> Path:
        """Warm up, then save one frame as JPEG. Returns the path."""
        for _ in range(self.warmup_frames):
            self._grab()
            time.sleep(0.05)
        frame = self._grab()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if self._grabber is not None:          # test path: frame is bytes
            path.write_bytes(frame if isinstance(frame, bytes) else b"FAKE")
        else:
            import cv2
            if not cv2.imwrite(str(path), frame):
                raise RuntimeError(f"could not write {path}")
        return path

    def close(self) -> None:
        if hasattr(self, "_cap"):
            self._cap.release()
            del self._cap
