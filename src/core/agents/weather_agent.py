"""
WeatherAgent returns weather information using WeatherService.
"""

from src.core.results import AgentResult

class WeatherAgent:
    def __init__(self, service):
        self.service = service

    def get(self, location: str):
        data = self.service.get_weather(location)
        return AgentResult(agent="weather", output=data)

