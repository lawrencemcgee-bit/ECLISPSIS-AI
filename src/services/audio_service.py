"""
AudioService placeholder for microphone input and waveform samples.
Milestone 6: simulated samples only (no real hardware).
"""

import math

class AudioService:
    def __init__(self):
        self.active = False
        self.phase = 0.0

    def start(self):
        self.active = True
        return True

    def stop(self):
        self.active = False
        return True

    def get_samples(self, count: int = 64):
        # Smooth sine wave with phase shift
        samples = []
        for i in range(count):
            samples.append(math.sin(self.phase + i * 0.15))
        self.phase += 0.2
        return samples

