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
    assistant.agents.run(
        "onenote",
        action="write",
        page="daily",
        content="Today's notes: System boot successful.",
    )
    print(
        "OneNote:", assistant.agents.run("onenote", action="open", page="daily").output
    )

    # Weather
    print("Weather:", assistant.agents.run("weather", location="San Antonio").output)

    # News
    print("News:", assistant.agents.run("news", category="technology").output)


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

