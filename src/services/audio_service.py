"""
AudioService — microphone capture and waveform samples.

Milestone 6: simulated-only (sine wave). This update adds real capture
via `sounddevice`, with the original simulation kept as an automatic
fallback — matching the graceful-degradation pattern already used
elsewhere (psutil in ObservabilityService, fastapi in the API layer).

Import guard note: `sounddevice` can fail in two different ways that both
need catching. A plain `ImportError` if the package itself isn't
installed, OR an `OSError` ("PortAudio library not found") if the
package IS installed but the underlying native PortAudio library isn't —
a genuinely common case on Linux systems that haven't separately
installed `libportaudio2`/`libportaudio-dev`, confirmed by hitting this
exact failure while developing this file. `except Exception` is used
deliberately broad here rather than `except ImportError` for that reason.
"""

import math
import threading

try:
    import sounddevice as sd
    import numpy as np
    REAL_AUDIO_AVAILABLE = True
except Exception:
    sd = None
    np = None
    REAL_AUDIO_AVAILABLE = False


class AudioService:
    def __init__(self, sample_rate: int = 16000, block_size: int = 1024):
        self.active = False
        self.phase = 0.0
        self.sample_rate = sample_rate
        self.block_size = block_size

        # Whether real capture is available in THIS environment — checked
        # once at import time (package + native lib present) and again,
        # more strictly, the first time start() actually tries to open a
        # device (present but no physical mic, OS permission denied,
        # device in use by another process, etc.). Either failure mode
        # falls back to the simulated sine wave, not a crash.
        self.real_capture_available = REAL_AUDIO_AVAILABLE

        self._stream = None
        self._lock = threading.Lock()
        self._latest_block = None
        self._pending_frames = []  # raw int16 PCM bytes, accumulated for STT

    def start(self):
        self.active = True
        if self.real_capture_available:
            try:
                self._start_real_stream()
            except Exception:
                # Device-level failure (no mic, OS denied it, in use
                # elsewhere) — degrade to simulation rather than crash,
                # for the rest of this process's lifetime.
                self.real_capture_available = False
                self._stream = None
        return True

    def _start_real_stream(self):
        def callback(indata, frames, time_info, status):
            mono = indata[:, 0].copy()
            with self._lock:
                self._latest_block = mono
                self._pending_frames.append((mono * 32767).astype(np.int16).tobytes())

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            blocksize=self.block_size,
            dtype="float32",
            callback=callback,
        )
        self._stream.start()

    def stop(self):
        self.active = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        return True

    def get_samples(self, count: int = 64):
        """Unchanged signature/behavior contract from Milestone 6 — Nova's
        waveform.py calls this with no knowledge of whether it's getting
        real or simulated data, by design."""
        if self.real_capture_available and self._latest_block is not None:
            with self._lock:
                block = self._latest_block
            if len(block) >= count:
                step = len(block) // count
                return [float(x) for x in block[::step][:count]]

        # Simulated fallback (original Milestone 6 behavior, unchanged).
        samples = []
        for i in range(count):
            samples.append(math.sin(self.phase + i * 0.15))
        self.phase += 0.2
        return samples

    def pop_transcription_audio(self) -> bytes:
        """Returns and clears raw PCM16 mono audio bytes (at
        self.sample_rate) accumulated since the last call — what
        VoiceService.transcribe_chunk() consumes. Returns b"" when
        real capture isn't active; there's nothing meaningful to
        transcribe from the simulated sine wave."""
        if not self.real_capture_available:
            return b""
        with self._lock:
            frames = self._pending_frames
            self._pending_frames = []
        return b"".join(frames)
