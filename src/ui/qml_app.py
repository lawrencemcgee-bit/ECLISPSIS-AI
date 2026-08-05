ffrom PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QUrl
import sys
import os

from src.core.assistant_core import AssistantCore
from src.ui.state_bridge import StateBridge

def run_qml_ui():
    app = QGuiApplication(sys.argv)
    engine = QQmlApplicationEngine()

    assistant = AssistantCore()
    bridge = StateBridge(assistant)

    assistant.events.on("state.changed",
        lambda payload: bridge.update_from_core(payload["new"])
    )

    engine.rootContext().setContextProperty("StateBridge", bridge)
    engine.rootContext().setContextProperty("ChatModel", bridge.chat)
    engine.rootContext().setContextProperty("assistant", assistant)

    qml_dir = os.path.dirname(__file__)
    engine.load(QUrl.fromLocalFile(os.path.join(qml_dir, "main_window.qml")))

    if not engine.rootObjects():
        sys.exit(-1)

    window = engine.rootObjects()[0]

    # Restore window size/position
    w = assistant.settings["window"]
    window.width = w["width"]
    window.height = w["height"]
    window.x = w["x"]
    window.y = w["y"]

    if w.get("maximized", False):
        window.showMaximized()

    # Connect signals for persistence
    window.widthChanged.connect(lambda: bridge.updateWindowSize(window.width, window.height))
    window.heightChanged.connect(lambda: bridge.updateWindowSize(window.width, window.height))
    window.xChanged.connect(lambda: bridge.updateWindowPosition(window.x, window.y))
    window.yChanged.connect(lambda: bridge.updateWindowPosition(window.x, window.y))

    sys.exit(app.exec())
