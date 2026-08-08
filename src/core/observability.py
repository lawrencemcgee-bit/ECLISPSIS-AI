"""
ObservabilityService — Phase 9: real metrics, health checks, and a
diagnostics snapshot, replacing the previously orphaned Observability class
(Milestone 2's print-based `log`/`metric` were never imported anywhere in
the codebase — this is a genuine gap fix, not a rewrite of working code).

Subscribes to the event bus so it can track counts/errors without every
subsystem needing to know about it directly, matching the pattern already
used by LoggingService and StateManager. AssistantCore owns "what does
healthy mean per subsystem" (it's the only thing that knows); this service
just aggregates whatever AssistantCore hands it into a single snapshot
shape, matching the prompt's Diagnostics Panel / GET /diagnostics intent.

System-level metrics (CPU/RAM/disk) use psutil if available and degrade
gracefully to {"available": False} if it isn't, so this doesn't become a
hard runtime dependency the way earlier placeholder services deliberately
avoided (Engineering Charter §5 — graceful degradation).
"""

import time

try:
    import psutil
except ImportError:  # pragma: no cover - environment-dependent
    psutil = None


class ObservabilityService:
    def __init__(self, events):
        self.events = events
        self.started_at = time.time()
        self.counters = {}
        self.last_error = None
        self._subscribe()

    # ---------------------------------------------------------
    # Event subscriptions
    # ---------------------------------------------------------
    def _subscribe(self):
        self.events.on("conversation.error", self._on_conversation_error)
        self.events.on("agent.failed", self._on_agent_failed)
        self.events.on("agent.completed", lambda p: self._increment("agent.completed"))
        self.events.on("conversation.processed", lambda p: self._increment("conversation.processed"))
        self.events.on("plugin.toggle", lambda p: self._increment("plugin.toggle"))
        self.events.on("nci.analysis.completed", lambda p: self._increment("nci.analysis.completed"))
        self.events.on("automation.completed", lambda p: self._increment("automation.completed"))
        self.events.on("automation.failed", self._on_automation_failed)
        self.events.on("state.changed", self._on_state_changed)

    def _on_state_changed(self, payload):
        new_state = payload.get("new") if payload else None
        if new_state:
            self._increment(f"state.{new_state}")

    def _on_conversation_error(self, payload):
        self._increment("conversation.error")
        self.last_error = {"event": "conversation.error", "payload": payload, "ts": time.time()}

    def _on_agent_failed(self, payload):
        self._increment("agent.failed")
        self.last_error = {"event": "agent.failed", "payload": payload, "ts": time.time()}

    def _on_automation_failed(self, payload):
        self._increment("automation.failed")
        self.last_error = {"event": "automation.failed", "payload": payload, "ts": time.time()}

    def _increment(self, key, amount=1):
        self.counters[key] = self.counters.get(key, 0) + amount

    # ---------------------------------------------------------
    # Metrics
    # ---------------------------------------------------------
    def uptime_seconds(self):
        return time.time() - self.started_at

    def system_metrics(self):
        if psutil is None:
            return {"available": False}
        try:
            return {
                "available": True,
                "cpu_percent": psutil.cpu_percent(interval=None),
                "ram_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage("/").percent,
            }
        except Exception:
            # Same graceful-degradation contract as an unavailable psutil —
            # a diagnostics panel should never crash the host it's diagnosing.
            return {"available": False}

    def snapshot(self, subsystems: dict):
        """subsystems: dict of subsystem_name -> status dict, supplied by
        AssistantCore since it's the only thing that owns each subsystem
        and knows what "healthy" means for it."""
        return {
            "uptime_seconds": self.uptime_seconds(),
            "counters": dict(self.counters),
            "last_error": self.last_error,
            "system": self.system_metrics(),
            "subsystems": subsystems,
        }
