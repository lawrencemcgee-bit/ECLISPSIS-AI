"""
Lyra's reactive avatar — parity work bringing Lyra's previously-static
avatar circle (see app.py's original docstring: "a static avatar circle
(no continuous pulse task)") up to the same state-reactivity Nova's orb
has, without copying Nova's ambient-glow visual language wholesale.

Deliberately lighter than orb.py: no BoxShadow glow layer (Lyra's whole
design point, per theme.py, is "minimal chrome" — a glowing halo would
undercut that), just the circle's own color and a subtle scale pulse.
Same composition pattern as orb.py/waveform.py: a plain ft.Container with
set_state/start_pulse/stop_pulse attached, not a Control subclass
(UserControl is deprecated ahead of Flet 1.0).

Confidence: MEDIUM, same caveats as orb.py — reviewed against Flet ~0.86
docs, not yet executed against a real install.
"""

import asyncio

import flet as ft

from src.ui_flet.personas.lyra import theme


def build_avatar(page: ft.Page, size: int = 64) -> ft.Container:
    icon = ft.Icon(ft.Icons.GRAPHIC_EQ, color=theme.ACCENT)
    avatar = ft.Container(
        width=size,
        height=size,
        border_radius=size,
        bgcolor=theme.ACCENT_DIM,
        border=ft.Border.all(2, theme.ACCENT),
        alignment=ft.Alignment.CENTER,
        content=icon,
        animate=ft.Animation(400, ft.AnimationCurve.EASE_OUT),
        animate_scale=ft.Animation(400, ft.AnimationCurve.EASE_IN_OUT),
    )

    _state = {"pulse_task": None, "current": "idle"}

    def set_state(name: str):
        color = theme.STATE_COLORS.get(name, theme.ACCENT_DIM)
        avatar.bgcolor = color
        avatar.border = ft.Border.all(2, color)
        avatar.update()
        _state["current"] = name

    async def _pulse_loop():
        big = False
        try:
            while True:
                big = not big
                # Subtler than Nova's orb (1.08/1.0) — a bigger swing on
                # a small 64px avatar reads as jittery rather than
                # ambient. Same idle/active-speed split as orb.py.
                avatar.scale = 1.04 if big else 1.0
                avatar.update()
                delay = 0.35 if _state["current"] in ("thinking", "listening") else 0.6
                await asyncio.sleep(delay)
        except asyncio.CancelledError:
            pass
        except Exception:
            # Window closed mid-loop — see orb.py's identical handling
            # for the confirmed real traceback this guards against.
            pass

    def start_pulse():
        if _state["pulse_task"] is None:
            _state["pulse_task"] = page.run_task(_pulse_loop)

    def stop_pulse():
        if _state["pulse_task"] is not None:
            _state["pulse_task"].cancel()
            _state["pulse_task"] = None

    avatar.set_state = set_state
    avatar.start_pulse = start_pulse
    avatar.stop_pulse = stop_pulse
    return avatar
