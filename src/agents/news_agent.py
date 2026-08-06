"""
NewsAgent returns news headlines using NewsService.
"""

from src.core.results import AgentResult

class NewsAgent:
    def __init__(self, service):
        self.service = service

    def get(self, category="general"):
        data = self.service.get_headlines(category)
        return AgentResult(agent="news", output=data)

