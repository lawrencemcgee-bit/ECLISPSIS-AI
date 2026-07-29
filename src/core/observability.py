"""
Observability hooks for logging, metrics, and tracing.
Milestone 2: structure only.
"""

class Observability:
    def log(self, message: str):
        print(f"[LOG] {message}")

    def metric(self, name: str, value):
        print(f"[METRIC] {name} = {value}")

