"""
Nova's reactive orb — the focal point of the Jarvis-style layout.

Built by composing plain ft.Stack/Container objects and attaching a few
extra methods directly onto the returned Stack, rather than subclassing
Flet's Control/UserControl. UserControl is deprecated as of Flet's 1.0
rewrite; composition-plus-attached-methods has no such deprecation risk
and is a common pattern in the Flet community for exactly this kind of
small stateful widget.

Confidence: MEDIUM. The layered-glow approach (a blurred, low-opacity
Container behind a solid core) is a reasonable approximation of a glow,
not true holographic rendering — Flet has no shader/GLSL access. The
continuous "breathing" pulse is a background asyncio loop toggling scale
on a timer; that's a real, small, ongoing cost for as long as the window
is open, not a free effect — worth profiling once this actually runs.

Version-sensitivity flag: Flet has historically split animation
properties (animate, animate_scale, animate_opacity, animate_rotation)
rather than having one `animate` cover everything. Both `animate` and
`animate_scale` are set below defensively; if the pulse doesn't visibly
animate on whatever version ends up installed, that split is the first
thing to check against current docs.flet.dev/controls/container.
"""

import asyncio

import flet as ft

from src.ui_flet.personas.nova import theme


def build_orb(page: ft.Page, size: int = 180) -> ft.Stack:
    core = ft.Container(
        width=size * 0.5,
        height=size * 0.5,
        border_radius=size,
        bgcolor=theme.ORB_IDLE_COLOR,
        animate=ft.Animation(400, ft.AnimationCurve.EASE_OUT),
        animate_scale=ft.Animation(400, ft.AnimationCurve.EASE_IN_OUT),
    )
    glow_outer = ft.Container(
        width=size,
        height=size,
        border_radius=size,
        bgcolor=ft.Colors.with_opacity(0.0, theme.ACCENT_GLOW),
        shadow=ft.BoxShadow(
            blur_radius=60,
            spread_radius=10,
            color=ft.Colors.with_opacity(0.35, theme.ACCENT_GLOW),
        ),
        animate=ft.Animation(400, ft.AnimationCurve.EASE_OUT),
        animate_scale=ft.Animation(400, ft.AnimationCurve.EASE_IN_OUT),
    )

    orb = ft.Stack(
        width=size,
        height=size,
        controls=[
            glow_outer,
            ft.Container(content=core, alignment=ft.Alignment.CENTER, width=size, height=size),
        ],
    )

    _state = {"pulse_task": None, "current": "idle"}

    def set_state(name: str):
        color = theme.STATE_COLORS.get(name, theme.ORB_IDLE_COLOR)
        core.bgcolor = color
        glow_outer.shadow.color = ft.Colors.with_opacity(0.45, color)
        core.update()
        glow_outer.update()
        _state["current"] = name

    async def _pulse_loop():
        big = False
        try:
            while True:
                big = not big
                core.scale = 1.08 if big else 1.0
                glow_outer.scale = 1.05 if big else 0.95
                core.update()
                glow_outer.update()
                # Faster pulse while listening/thinking than at idle — a
                # cheap way to make the orb read as state-reactive beyond
                # just its color.
                delay = 0.35 if _state["current"] in ("thinking", "listening") else 0.6
                await asyncio.sleep(delay)
        except asyncio.CancelledError:
            pass
        except Exception:
            # Most commonly: the window was closed while this loop was
            # mid-iteration, and core.update() tried to reach an
            # already-destroyed Flet session — confirmed via a real
            # traceback, not hypothetical. A background loop hitting that
            # should just stop quietly, not crash the app on exit.
            pass

    def start_pulse():
        if _state["pulse_task"] is None:
            _state["pulse_task"] = page.run_task(_pulse_loop)

    def stop_pulse():
        if _state["pulse_task"] is not None:
            _state["pulse_task"].cancel()
            _state["pulse_task"] = None

    orb.set_state = set_state
    orb.start_pulse = start_pulse
    orb.stop_pulse = stop_pulse
    return orb
