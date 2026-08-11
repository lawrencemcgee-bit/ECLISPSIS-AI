"""
Lyra's permissions panel — same dialog Nova has, Lyra's amber theme
colors. See src/ui_flet/shared_dialogs.py for the actual logic and
src/ui_flet/personas/nova/permissions_dialog.py for the full reasoning
(proactive grant, not a blocking mid-request popup).
"""

import flet as ft

from src.ui_flet.personas.lyra import theme
from src.ui_flet.shared_dialogs import build_permissions_button as _build


def build_permissions_button(page: ft.Page, assistant) -> ft.IconButton:
    return _build(page, assistant, accent=theme.ACCENT, muted=theme.TEXT_MUTED)
