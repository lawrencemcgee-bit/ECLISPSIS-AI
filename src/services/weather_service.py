"""
WeatherService provides simple weather lookup.
Milestone 3: static data (no API calls).
"""

class WeatherService:
    def get_weather(self, location: str):
        return {
            "location": location,
            "temperature": "92°F",
            "condition": "Clear skies",
            "humidity": "40%"
        }

