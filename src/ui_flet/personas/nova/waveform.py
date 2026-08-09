"""
Nova's waveform visualizer — a row of bars driven by AudioService's
simulated samples (src/services/audio_service.py: 64 floats in [-1, 1]).

Same composition pattern as orb.py: a real ft.Row with a set_samples()
method attached, not a Control subclass. FletBridge._render_waveform()
calls set_samples() if present (see src/ui_flet/bridge.py) — this is
where that hook is actually implemented for the Nova persona.
"""

import flet as ft

from src.ui_flet.personas.nova import theme

BAR_COUNT = 32  # downsample from AudioService's 64 samples for a cleaner look
BAR_WIDTH = 4
MAX_BAR_HEIGHT = 48


def build_waveform() -> ft.Row:
    bars = [
        ft.Container(
            width=BAR_WIDTH,
            height=2,
            bgcolor=theme.ACCENT,
            border_radius=2,
            animate=ft.Animation(80, ft.AnimationCurve.EASE_OUT),
        )
        for _ in range(BAR_COUNT)
    ]

    row = ft.Row(
        controls=bars,
        alignment=ft.MainAxisAlignment.CENTER,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=3,
        height=MAX_BAR_HEIGHT,
    )

    def set_samples(samples):
        step = max(1, len(samples) // BAR_COUNT)
        downsampled = samples[::step][:BAR_COUNT]
        for bar, sample in zip(bars, downsampled):
            bar.height = max(2, abs(sample) * MAX_BAR_HEIGHT)

    row.set_samples = set_samples
    return row
