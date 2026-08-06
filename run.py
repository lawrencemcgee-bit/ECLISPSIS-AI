"""
Startup script for ECLIPSIS-AI.
Runs the assistant core and launches the QML UI.
Also demonstrates agent usage (OneNote, Weather, News).
"""

from src.core.assistant_core import AssistantCore
from src.ui.qml_app import run_qml_ui

def demo_agents(assistant: AssistantCore):
    print("\n=== Agent Demo ===")

    # OneNote
    onenote = assistant.agents.registry.get("onenote")
    onenote.write("daily", "Today's notes: System boot successful.")
    print("OneNote:", onenote.open("daily").output)

    # Weather
    weather = assistant.agents.registry.get("weather")
    print("Weather:", weather.get("San Antonio").output)

    # News
    news = assistant.agents.registry.get("news")
    print("News:", news.get("technology").output)

if __name__ == "__main__":
    assistant = AssistantCore()

    # CLI conversation demo
    result = assistant.process_message("Hello assistant")
    print("Conversation:", result.content)

    # Agent demo
    demo_agents(assistant)

    # Launch QML UI using the SAME assistant instance — not a second one.
    # (Phase 2: previously qml_app.py constructed its own AssistantCore(),
    # meaning the CLI demo above and the UI ran against two unrelated
    # instances with separate settings/session/logging state.)
    print("Launching QML UI...")
    run_qml_ui(assistant)

