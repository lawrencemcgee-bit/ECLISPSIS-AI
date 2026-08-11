"""
Lyra's waveform visualizer — parity work; Lyra previously had no
waveform wired in at all (see app.py's original docstring). Same
AudioService.get_samples() data source and downsampling approach as
Nova's waveform.py, sized smaller and placed in the command bar rather
than as a large central visualizer — Lyra's console layout has no
orb-sized focal area for it to live in, and a voice-first persona's
waveform reads naturally as a meter next to the mic button, not a
centerpiece.
"""

import flet as ft

from src.ui_flet.personas.lyra import theme

BAR_COUNT = 20  # fewer than Nova's 32 — sized for the command bar, not a centerpiece
BAR_WIDTH = 3
MAX_BAR_HEIGHT = 24


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
        spacing=2,
        height=MAX_BAR_HEIGHT,
    )

    def set_samples(samples):
        step = max(1, len(samples) // BAR_COUNT)
        downsampled = samples[::step][:BAR_COUNT]
        for bar, sample in zip(bars, downsampled):
            bar.height = max(2, abs(sample) * MAX_BAR_HEIGHT)

    row.set_samples = set_samples
    return row
