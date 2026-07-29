"""
OneNoteService handles opening, reading, and writing OneNote pages.
Milestone 3: local file-based simulation (no API calls).
"""

import os

class OneNoteService:
    def __init__(self, base="onenote"):
        self.base = base
        os.makedirs(self.base, exist_ok=True)

    def open_page(self, name: str):
        path = os.path.join(self.base, f"{name}.txt")
        if not os.path.exists(path):
            return ""
        with open(path, "r") as f:
            return f.read()

    def write_page(self, name: str, content: str):
        path = os.path.join(self.base, f"{name}.txt")
        with open(path, "w") as f:
            f.write(content)
        return True

