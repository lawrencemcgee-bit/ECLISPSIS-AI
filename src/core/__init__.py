"""
Core module initialization for ECLISPSIS-AI.
Contains foundational types, state models, the event bus, and result formats.
"""

--- eclipsis/ECLISPSIS-AI-main/src/core/__init__.py	2026-08-05 02:41:41.000000000 +0000
+++ eclipsis_fixed/src/core/__init__.py	2026-08-05 03:26:49.313446096 +0000
@@ -1,8 +1,5 @@
 """
 Core module initialization for ECLISPSIS-AI.
-Contains foundational types, state models, events, dispatcher, and result formats.
+Contains foundational types, state models, the event bus, and result formats.
 """
-self.agents.registry.register("onenote", OneNoteAgent(OneNoteService()))
-self.agents.registry.register("weather", WeatherAgent(WeatherService()))
-self.agents.registry.register("news", NewsAgent(NewsService()))