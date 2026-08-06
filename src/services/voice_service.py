"""
VoiceService — Phase 7: tracks real listening state instead of returning
static strings with no state (Milestone 1 placeholder). Still no real
speech-to-text engine or microphone access — that requires a real STT
dependency (e.g. whisper/vosk) and actual hardware to test against, neither
of which exist in this project yet. simulate_command() stands in for what a
real STT engine would eventually call once transcription happens.
"""

class VoiceService:
    def __init__(self):
        self.listening = False

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

    def simulate_command(self, text: str):
        """Stand-in for what a real STT engine would produce once speech is
        transcribed. Real capture is future work — see class docstring."""
        return text


