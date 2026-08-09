"""
Flet entry point — a THIRD frontend on the same AssistantCore, alongside
run.py (QML desktop) and api.py (HTTP). Same "one shared instance"
principle as both of those.

Usage:
    python flet_run.py                 # Nova (default)
    python flet_run.py --persona lyra  # Lyra
    python flet_run.py --web           # run in a browser instead of a
                                        # native window (Flet supports
                                        # both from the same code)

This does not replace run.py or api.py — all three can coexist. Whether
QML is deprecated/removed later is a separate decision from whether this
file exists.
"""

import argparse

import flet as ft

from src.core.assistant_core import AssistantCore
from src.ui_flet.personas.nova.app import create_nova_app
from src.ui_flet.personas.lyra.app import create_lyra_app

PERSONAS = {
    "nova": create_nova_app,
    "lyra": create_lyra_app,
}


def main():
    parser = argparse.ArgumentParser(description="Run the Flet UI for ECLIPSIS-AI")
    parser.add_argument("--persona", choices=sorted(PERSONAS), default="nova")
    parser.add_argument("--web", action="store_true", help="Run in a browser instead of a native window")
    args = parser.parse_args()

    assistant = AssistantCore()

    # Same tick-wiring decision made in Milestone 13 for qml_app.py and
    # api.py — schedule-based automations need something to call
    # automation_tick() periodically, regardless of which frontend is
    # hosting AssistantCore.
    assistant.start_automation_ticker()

    target = PERSONAS[args.persona](assistant)

    if args.web:
        ft.run(target, view=ft.AppView.WEB_BROWSER)
    else:
        ft.run(target)

    assistant.stop_automation_ticker()


if __name__ == "__main__":
    main()
