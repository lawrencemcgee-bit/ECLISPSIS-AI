"""
Nova — Approach 1 design tokens. "Jarvis-style": a dark, glass-panelled
command center with a reactive central orb and a holographic-blue palette.

Confidence note: color choices and layout are a genuine design opinion,
not a verified fact — reasonable starting point, not the only valid one.
The one thing to flag clearly: Flet has no arbitrary shader/GLSL support,
so "holographic" here means layered semi-transparent glow (BoxShadow +
low-opacity Containers + backdrop blur), not true volumetric rendering.
That's a real fidelity ceiling relative to what "holographic" usually
implies visually — achievable, but it will read as "glowing glass," not
as an actual hologram.
"""

import flet as ft

BACKGROUND = "#05070D"
PANEL = "#0D1420"
PANEL_BORDER = "#1B2A3D"
ACCENT = "#00D9FF"
ACCENT_DIM = "#0A5A6E"
ACCENT_GLOW = "#00D9FF"
TEXT_PRIMARY = "#E6F7FF"
TEXT_MUTED = "#5C7A8C"
DANGER = "#FF4D6D"

ORB_IDLE_COLOR = ACCENT_DIM
ORB_LISTENING_COLOR = ACCENT
ORB_THINKING_COLOR = "#7B61FF"
ORB_ERROR_COLOR = DANGER

STATE_COLORS = {
    "idle": ORB_IDLE_COLOR,
    "listening": ACCENT,
    "thinking": ORB_THINKING_COLOR,
    "speaking": ACCENT,
    "error": ORB_ERROR_COLOR,
}


def glass_panel(content, width=None, height=None, padding=16, expand=False):
    """A semi-transparent, blurred, thin-bordered container — Flet's
    closest approximation to a glassmorphic HUD panel."""
    return ft.Container(
        content=content,
        width=width,
        height=height,
        expand=expand,
        padding=padding,
        bgcolor=ft.Colors.with_opacity(0.35, PANEL),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.4, PANEL_BORDER)),
        border_radius=16,
        blur=ft.Blur(10, 10, ft.BlurTileMode.CLAMP),
    )


def page_theme() -> ft.Theme:
    return ft.Theme(color_scheme_seed=ACCENT, use_material3=True)
