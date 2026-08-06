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

    def execute(self, action: str, **kwargs):
        """Uniform entry point for AgentRegistry/AgentRouter dispatch.
        Delegates to the existing open()/write() methods — added in Phase 3
        so agents can be routed through the registry generically without
        changing their original per-agent methods."""
        if action == "open":
            return self.open(kwargs["page"])
        if action == "write":
            return self.write(kwargs["page"], kwargs["content"])
        return AgentResult(agent="onenote", output=None,
                            metadata={"error": f"unknown action '{action}'"})


