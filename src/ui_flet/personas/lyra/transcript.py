"""
Lyra's console-styled transcript line builder — parity work. Previously
Lyra reused FletBridge's default chat-bubble renderer verbatim (see
app.py's original docstring), which reads as a generic chat app and
undercuts the "monospace terminal" design language theme.py describes.

Passed into FletBridge.attach(bubble_builder=...) — see bridge.py, where
that parameter existed only as a docstring promise until this needed it.

Renders each turn as a single monospace line — "> you: ..." /
"agentname: ..." — rather than Nova's boxed bubbles, matching Lyra's
slash-command / terminal framing.
"""

import flet as ft

from src.ui_flet.personas.lyra import theme

# sender values seen in practice: "user", "assistant", and agent ids
# (onenote/weather/news) from FletBridge.run_selected_agent(), plus
# "system" for the unknown-agent fallback path.
LABELS = {
    "user": "you",
    "assistant": "lyra",
    "system": "system",
}


def build_console_line(sender: str, text: str) -> ft.Control:
    label = LABELS.get(sender, sender)
    color = theme.ACCENT if sender == "user" else theme.TEXT_PRIMARY
    prefix = "> " if sender == "user" else ""
    return ft.Text(
        f"{prefix}{label}: {text}",
        font_family=theme.CONSOLE_FONT,
        color=color,
        selectable=True,
        size=13,
    )
