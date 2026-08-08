"""
Process entry point for `uvicorn api:app --reload` — that exact target has
been sitting in the Makefile since before this milestone (`start-api`) with
no module for it to point at. This constructs the one shared AssistantCore
instance the same way run.py does for the QML UI, then hands it to
create_app() (src/api/api_app.py) — same "single shared instance"
principle as run_qml_ui(assistant), different frontend.
"""

from src.core.assistant_core import AssistantCore
from src.api.api_app import create_app

assistant = AssistantCore()

# Phase 13: schedule-based automations need something to call tick()
# periodically, same as qml_app.py's desktop entry point — see
# AssistantCore.start_automation_ticker's docstring for why this is a
# plain background thread rather than something tied to uvicorn/asyncio.
assistant.start_automation_ticker()

app = create_app(assistant)
