"""
VisionService — camera capture + local, non-LLM image analysis.

Milestone 6 shipped this fully simulated: capture() returned a fixed
placeholder string and never touched a camera. Tier 3 adds real capture
via OpenCV (`cv2`), with that original placeholder kept as an automatic
fallback — the same graceful-degradation pattern AudioService/VoiceService
already use for sounddevice/vosk (see audio_service.py's docstring): an
import-level check for whether the package is present, plus a
device-level check the first time a capture is actually attempted
(package present but no physical camera, OS permission denied, device in
use elsewhere, etc.). Either failure mode degrades to the simulated
result for the rest of this process's lifetime, never a crash.

Analysis is local/heuristic, matching NCIService's design elsewhere in
this codebase: no external vision-model API call. A captured frame is
described using real pixel-level signals — resolution, brightness,
sharpness (blur detection via Laplacian variance), and dominant color
channel — not an ML classification of what's depicted. That's an honest
scope: useful signal about the frame itself, not object/scene
recognition, which would need a real model this project doesn't have.
"""

import os
import time

try:
    import cv2
    import numpy as np
    REAL_VISION_AVAILABLE = True
except Exception:
    cv2 = None
    np = None
    REAL_VISION_AVAILABLE = False

# Same escape hatch as ECLIPSIS_FORCE_SIMULATED_AUDIO/_VOICE — tests must
# never depend on or exercise real camera hardware. test_all_phases.py
# sets this before running.
FORCE_SIMULATED_VISION = os.environ.get("ECLIPSIS_FORCE_SIMULATED_VISION") == "1"


class VisionService:
    def __init__(self, capture_dir: str = "data/vision_captures", camera_index: int = 0):
        # Whether real capture is available in THIS environment — checked
        # once at import time (package present) and again, more
        # strictly, the first time capture() actually tries to open a
        # device. See module docstring.
        self.camera_available = REAL_VISION_AVAILABLE and not FORCE_SIMULATED_VISION
        self.camera_index = camera_index
        self.capture_dir = capture_dir

    def capture(self):
        if self.camera_available:
            try:
                return self._capture_real()
            except Exception as exc:
                self.camera_available = False
                return self._capture_simulated(reason=str(exc))
        return self._capture_simulated()

    def _capture_real(self):
        cap = cv2.VideoCapture(self.camera_index)
        try:
            if not cap.isOpened():
                raise RuntimeError(f"Camera index {self.camera_index} could not be opened.")
            ok, frame = cap.read()
            if not ok or frame is None:
                raise RuntimeError("Camera opened but returned no frame.")
        finally:
            cap.release()

        os.makedirs(self.capture_dir, exist_ok=True)
        filename = f"capture_{int(time.time() * 1000)}.jpg"
        path = os.path.join(self.capture_dir, filename)
        cv2.imwrite(path, frame)

        return {
            "simulated": False,
            "path": path,
            **self._analyze_frame(frame),
        }

    def _analyze_frame(self, frame) -> dict:
        height, width = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        brightness = float(np.mean(gray))
        # Laplacian variance is a standard, well-established blur proxy:
        # a sharp image has strong edges (high-variance second
        # derivative); a blurry one is smooth (low variance).
        sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        # OpenCV loads frames as BGR, not RGB.
        b_mean = float(np.mean(frame[:, :, 0]))
        g_mean = float(np.mean(frame[:, :, 1]))
        r_mean = float(np.mean(frame[:, :, 2]))
        channels = {"red": r_mean, "green": g_mean, "blue": b_mean}
        dominant_channel = max(channels, key=channels.get)

        return {
            "resolution": {"width": width, "height": height},
            "brightness": round(brightness, 1),
            "sharpness": round(sharpness, 1),
            "dominant_channel": dominant_channel,
            "channel_means": {k: round(v, 1) for k, v in channels.items()},
        }

    def _capture_simulated(self, reason: str = None) -> dict:
        if reason is None:
            reason = ("No camera backend available in this environment."
                       if not REAL_VISION_AVAILABLE else
                       "Real capture disabled or unavailable for this process.")
        return {
            "simulated": True,
            "reason": reason,
            "placeholder": "vision_capture_placeholder",
        }
