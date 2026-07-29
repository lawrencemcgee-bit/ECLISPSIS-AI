"""
NewsService provides simple news headlines.
Milestone 3: static data (no API calls).
"""

class NewsService:
    def get_headlines(self, category="general"):
        return {
            "category": category,
            "headlines": [
                "AI breakthroughs accelerate global innovation",
                "Tech companies expand into new markets",
                "Major updates released across software ecosystems"
            ]
        }

