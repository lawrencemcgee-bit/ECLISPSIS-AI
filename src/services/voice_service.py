"""
VoiceService — Phase 7 was a listening-state machine only; simulate_command()
stood in for what real speech-to-text would eventually produce. This update
adds real STT (Vosk — offline, free, no API key) and real TTS (pyttsx3 —
offline, free, uses whatever voices are already installed on the OS), both
optional at runtime with the same graceful-degradation pattern used
elsewhere (psutil, fastapi, sounddevice).

Vosk needs more than `pip install vosk` — it needs a downloaded model
directory, which is NOT bundled here (models run tens to hundreds of MB
and downloading one wasn't done blindly). See docs/voice_io_assessment.md
for the exact model URL and where to put it. Without a model present,
stt_available stays False and simulate_command() keeps working exactly as
before — nothing breaks, voice commands just aren't real yet until a
model is in place.
"""

import json
import os
import threading

try:
    import vosk
except ImportError:
    vosk = None

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

# Same escape hatch as audio_service.py's FORCE_SIMULATED_AUDIO, and same
# reasoning: a test suite should never touch real hardware/engines, full
# stop, independent of whether doing so happens to be safe. pyttsx3.init()
# in particular was running fresh on every one of the ~15+ tests that
# construct an AssistantCore() before this — wasteful at minimum, and a
# real risk of SAPI5 reentrancy issues on Windows from repeated init()
# calls, not to mention a test suite that audibly talks during a run.
FORCE_SIMULATED_VOICE = os.environ.get("ECLIPSIS_FORCE_SIMULATED_VOICE") == "1"

DEFAULT_MODEL_PATH = os.path.join("models", "vosk-model-small-en-us-0.15")


class VoiceService:
    def __init__(self, sample_rate: int = 16000, model_path: str = None):
        self.listening = False
        self.sample_rate = sample_rate

        self.stt_available = False
        self._recognizer = None
        if not FORCE_SIMULATED_VOICE:
            self._init_stt(model_path or DEFAULT_MODEL_PATH)

        self.tts_available = False
        self._tts_engine = None
        self._tts_lock = threading.Lock()
        if not FORCE_SIMULATED_VOICE:
            self._init_tts()

    def _init_stt(self, model_path: str):
        if vosk is None or not os.path.isdir(model_path):
            return
        try:
            vosk.SetLogLevel(-1)  # Vosk logs to stderr by default; quiet unless something's actually asked for it
            model = vosk.Model(model_path)
            self._recognizer = vosk.KaldiRecognizer(model, self.sample_rate)
            self.stt_available = True
        except Exception:
            self.stt_available = False
            self._recognizer = None

    def _init_tts(self):
        if pyttsx3 is None:
            return
        try:
            self._tts_engine = pyttsx3.init()
            self.tts_available = True
        except Exception:
            self._tts_engine = None
            self.tts_available = False

    def start_listening(self):
        """Returns True if this call actually changed state (was not
        already listening), False if it was a no-op."""
        if self.listening:
            return False
        self.listening = True
        return True

    def stop_listening(self):
        """Returns True if this call actually changed state, False if it
        was already stopped."""
        if not self.listening:
            return False
        self.listening = False
        return True

    def transcribe_chunk(self, audio_bytes: bytes):
        """Feeds raw PCM16 mono audio bytes (at self.sample_rate) into
        the STT engine. Returns finalized text once Vosk considers an
        utterance complete, or None otherwise — mid-utterance with
        nothing final yet, no audio given, or STT unavailable. None
        means "nothing to act on yet," not an error; callers should
        keep calling this as more audio arrives rather than treating a
        None as a failure."""
        if not self.stt_available or not audio_bytes:
            return None
        if self._recognizer.AcceptWaveform(audio_bytes):
            result = json.loads(self._recognizer.Result())
            text = result.get("text", "").strip()
            return text or None
        return None

    def simulate_command(self, text: str):
        """Original Milestone 7 placeholder, kept as-is — still exactly
        what it was: an identity pass-through representing "pretend this
        text came from STT." Used when no real STT is available."""
        return text

    def speak(self, text: str) -> bool:
        """Non-blocking: pyttsx3's runAndWait() blocks the calling thread
        until speech finishes, which would freeze whatever event loop
        called this (Flet's asyncio loop, Qt's main thread) — run on a
        background thread instead. Returns False immediately (not
        queued) if TTS isn't available or text is empty."""
        if not self.tts_available or not text:
            return False

        def _run():
            with self._tts_lock:
                self._tts_engine.say(text)
                self._tts_engine.runAndWait()

        threading.Thread(target=_run, daemon=True).start()
        return True

    def list_voices(self):
        """Whatever voices are already installed on this OS (Windows
        SAPI5, macOS NSSpeechSynthesizer voices, espeak on Linux) —
        genuinely free, no licensing, no API key, but also whatever
        happens to be installed rather than a curated set."""
        if not self.tts_available:
            return []
        return [{"id": v.id, "name": v.name} for v in self._tts_engine.getProperty("voices")]

    def set_voice(self, voice_id: str):
        if self.tts_available:
            self._tts_engine.setProperty("voice", voice_id)
