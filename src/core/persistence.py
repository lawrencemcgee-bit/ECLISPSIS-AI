"""
File-based persistence for long-term memory and task history.
Milestone 3: JSON storage.
"""

import json
import os

class Persistence:
    def __init__(self, path="data"):
        self.path = path
        os.makedirs(self.path, exist_ok=True)

    def save(self, name: str, data: dict):
        with open(os.path.join(self.path, f"{name}.json"), "w") as f:
            json.dump(data, f, indent=2)

    def load(self, name: str):
        file_path = os.path.join(self.path, f"{name}.json")
        if not os.path.exists(file_path):
            return {}
        with open(file_path, "r") as f:
            return json.load(f)

