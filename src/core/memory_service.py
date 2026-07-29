"""
MemoryService handles short-lived context and persistent memory.
Milestone 2: structure only.
"""

class MemoryService:
    def __init__(self):
        self.short_term = {}
        self.long_term = {}

    def remember(self, key: str, value):
        self.short_term[key] = value

    def recall(self, key: str):
        return self.short_term.get(key)

