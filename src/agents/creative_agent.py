"""
CreativeAgent — local template/procedural generation and heuristic
critique via CreativeContentService. No LLM; see that service's module
docstring for why and what that means for the honesty of its output.
"""

from src.core.results import AgentResult


class CreativeAgent:
    def __init__(self, service):
        self.service = service

    def headlines(self, topic: str, count: int = 5, seed: int = None):
        data = self.service.generate_headlines(topic, count, seed)
        return AgentResult(agent="creative", output={"headlines": data})

    def writing_prompt(self, genre: str = None, seed: int = None):
        data = self.service.generate_writing_prompt(genre, seed)
        return AgentResult(agent="creative", output=data)

    def outline(self, topic: str, content_type: str = "blog_post"):
        data = self.service.generate_outline(topic, content_type)
        return AgentResult(agent="creative", output=data)

    def critique(self, text: str):
        data = self.service.critique(text)
        return AgentResult(agent="creative", output=data)

    def execute(self, action: str = "headlines", **kwargs):
        """Uniform entry point for AgentRegistry/AgentRouter dispatch."""
        if action == "headlines":
            return self.headlines(kwargs["topic"], kwargs.get("count", 5), kwargs.get("seed"))
        if action == "writing_prompt":
            return self.writing_prompt(kwargs.get("genre"), kwargs.get("seed"))
        if action == "outline":
            return self.outline(kwargs["topic"], kwargs.get("content_type", "blog_post"))
        if action == "critique":
            return self.critique(kwargs["text"])
        return AgentResult(agent="creative", output=None,
                            metadata={"error": f"unknown action '{action}'"})
