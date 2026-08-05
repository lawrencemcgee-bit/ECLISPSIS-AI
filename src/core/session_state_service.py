"""
SessionStateService: volatile UI/session state persistence.
Milestone 7 Step 10: restore open panels, draft input, last view.
"""

import json
import os

class SessionStateService:
    def __init__(self):
        self.base_dir = os.path.join(os.getcwd(), "data")
        self.path = os.path.join(self.base_dir, "session_state.json")
        self._ensure_dirs()

    def _ensure_dirs(self):
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)

    def load(self):
        if not os.path.exists(self.path):
            return {
                "panels": {
                    "settings": False,
                    "profile": False,
                    "logs": False,
                    "quick": False
                },
                "draft": "",
                "last_agent": "onenote",
                "crashed": False
            }
        with open(self.path, "r") as f:
            return json.load(f)

    def save(self, state: dict):
        with open(self.path, "w") as f:
            json.dump(state, f, indent=4)
