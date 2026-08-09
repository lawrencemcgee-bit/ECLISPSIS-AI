"""
Lyra — Approach 2 design tokens. Voice-first command console: minimal
chrome, a static persona avatar rather than Nova's ambient animated orb,
and a monospace transcript styled like a terminal. Warm neutral palette
deliberately distinct from Nova's electric blue, so the two feel like
genuinely different products, not reskins of the same layout.

Confidence: MEDIUM — same caveat as Nova's theme.py: a design opinion,
not a verified fact.
"""

import flet as ft

BACKGROUND = "#12100E"
PANEL = "#1C1917"
PANEL_BORDER = "#33302C"
ACCENT = "#E8A96B"       # warm amber, replacing Nova's cyan
ACCENT_DIM = "#7A5B3A"
TEXT_PRIMARY = "#F2EAE0"
TEXT_MUTED = "#9C8F7E"
DANGER = "#E85D5D"

CONSOLE_FONT = "Consolas, Menlo, monospace"


def console_panel(content, expand=False, height=None):
    return ft.Container(
        content=content,
        expand=expand,
        height=height,
        bgcolor=ft.Colors.with_opacity(0.9, PANEL),
        border=ft.Border.all(1, PANEL_BORDER),
        border_radius=8,
        padding=16,
    )


def page_theme() -> ft.Theme:
    return ft.Theme(color_scheme_seed=ACCENT, use_material3=True)
