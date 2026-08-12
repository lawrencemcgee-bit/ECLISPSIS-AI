"""
Packaging entry point for `flet build` — Nova persona only.

flet_run.py (the dev entry point) picks a persona via a --persona CLI
flag, but a packaged native app has no CLI args to hand it the way
`python flet_run.py --persona lyra` does. Rather than build one package
that guesses or needs an in-app selector, each persona gets its own
dedicated, hardcoded entry point and its own separate build — see
lyra_main.py for the other one, and docs/flet_packaging.md for the
actual `flet build` invocations.

Not a copy of flet_run.py's logic with argparse stripped out: it reuses
the same AssistantCore + create_nova_app + automation-ticker wiring
flet_run.py already established (Milestone 13's tick-wiring decision),
just without the persona-selection/--web branching that only make sense
for local dev runs.
"""

import flet as ft

from src.core.assistant_core import AssistantCore
from src.ui_flet.personas.nova.app import create_nova_app


def main():
    assistant = AssistantCore()
    assistant.start_automation_ticker()
    target = create_nova_app(assistant)
    try:
        ft.run(target)
    finally:
        assistant.stop_automation_ticker()


if __name__ == "__main__":
    main()
