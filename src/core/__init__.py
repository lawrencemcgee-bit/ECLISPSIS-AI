"""
Core module initialization for ECLISPSIS-AI.
Contains foundational types, state models, events, dispatcher, and result formats.
"""
self.agents.registry.register("onenote", OneNoteAgent(OneNoteService()))
self.agents.registry.register("weather", WeatherAgent(WeatherService()))
self.agents.registry.register("news", NewsAgent(NewsService()))

