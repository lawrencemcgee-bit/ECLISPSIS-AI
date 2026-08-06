"""
MemoryService handles short-lived context and persistent (long-term) memory.
Phase 5: long-term memory is now backed by PersistenceService instead of
being an unused in-memory dict — short-term memory is unchanged.
"""

class MemoryService:
    def __init__(self, persistence):
        self.short_term = {}
        self._persistence = persistence
        self.long_term = self._persistence.load_memory()

    def remember(self, key: str, value):
        self.short_term[key] = value

    def recall(self, key: str):
        return self.short_term.get(key)

    def remember_long_term(self, key: str, value):
        """Write-through: updates in-memory long_term AND persists
        immediately, so a memory write can't be silently lost if nothing
        calls an explicit save() before the app closes."""
        self.long_term[key] = value
        self._persistence.save_memory(self.long_term)

    def recall_long_term(self, key: str):
        return self.long_term.get(key)

