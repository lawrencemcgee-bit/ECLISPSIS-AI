"""
OneNoteAgent provides read/write access to OneNote pages.
"""

from src.core.results import AgentResult

class OneNoteAgent:
    def __init__(self, service):
        self.service = service

    def open(self, page: str):
        content = self.service.open_page(page)
        return AgentResult(agent="onenote", output=content)

    def write(self, page: str, content: str):
        self.service.write_page(page, content)
        return AgentResult(agent="onenote", output=f"Page '{page}' updated.")

