"""
PersistenceService handles saving/loading settings, chat history, agent data,
and long-term memory.
Milestone 7: JSON-based persistence with safe defaults + window state.
"""

import json
import os

class PersistenceService:
    def __init__(self):
        self.base_dir = os.path.join(os.getcwd(), "data")
        self.settings_path = os.path.join(self.base_dir, "settings.json")
        self.chat_path = os.path.join(self.base_dir, "chat_history.json")
        self.memory_path = os.path.join(self.base_dir, "memory.json")

        self._ensure_dirs()

    def _ensure_dirs(self):
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)

    # -----------------------------
    # Settings
    # -----------------------------
    def load_settings(self):
        if not os.path.exists(self.settings_path):
            return {
                "theme": "dark",
                "last_agent": "onenote",
                "mic_enabled": False,
                "window": {
                    "width": 960,
                    "height": 540,
                    "x": 100,
                    "y": 100,
                    "maximized": False
                }
            }
        with open(self.settings_path, "r") as f:
            return json.load(f)

    def save_settings(self, settings: dict):
        with open(self.settings_path, "w") as f:
            json.dump(settings, f, indent=4)

    # -----------------------------
    # Chat History
    # -----------------------------
    def load_chat_history(self):
        if not os.path.exists(self.chat_path):
            return []
        with open(self.chat_path, "r") as f:
            return json.load(f)

    def save_chat_history(self, chat_list: list):
        with open(self.chat_path, "w") as f:
            json.dump(chat_list, f, indent=4)

    # -----------------------------
    # Long-Term Memory (Phase 5)
    # -----------------------------
    def load_memory(self):
        if not os.path.exists(self.memory_path):
            return {}
        with open(self.memory_path, "r") as f:
            return json.load(f)

    def save_memory(self, memory: dict):
        with open(self.memory_path, "w") as f:
            json.dump(memory, f, indent=4)

