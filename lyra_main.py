"""
Packaging entry point for `flet build` — Lyra persona only.

See nova_main.py's module docstring — same reasoning, mirrored for the
other persona. Kept as two near-identical files rather than one
parameterized file because a packaged app's entry point can't take the
--persona argument that makes flet_run.py's single file work for local
dev; each persona needs its own unambiguous, argument-free `main()`.
"""

import flet as ft

from src.core.assistant_core import AssistantCore
from src.ui_flet.personas.lyra.app import create_lyra_app


def main():
    assistant = AssistantCore()
    assistant.start_automation_ticker()
    target = create_lyra_app(assistant)
    try:
        ft.run(target)
    finally:
        assistant.stop_automation_ticker()


if __name__ == "__main__":
    main()
