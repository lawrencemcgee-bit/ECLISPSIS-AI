"""
AutomationService (Phase 12, persistence added in Phase 13) — schedule- and
event-based triggers so the assistant can act proactively instead of
purely in response to a message.

Two trigger kinds:
- "event": fires when a named event bus event occurs, optionally filtered
  by a predicate over that event's payload
- "schedule": fires when tick() is called and the trigger's next_run has
  passed; recurring triggers reschedule themselves by interval_seconds

Deliberately NOT a background thread or real-time scheduler itself:
tick() must be called by something else. AssistantCore.start_automation_
ticker() (Phase 13) is what actually calls it periodically in a running
process — see that method's docstring for why ticking lives there rather
than in this class.

Actions are declarative dicts, not arbitrary callables, resolved by an
injected executor rather than executed here directly. That keeps
AutomationService from needing to import AssistantCore (avoiding a
circular import) and means every automated action goes through the same
capabilities (agents/plugins/messages) — and whatever verification or
permission checks those already have — that a manual request would.

Persistence (Phase 13): each trigger is registered with persistent=True
or False. Only persistent triggers are written to disk (via
PersistenceService's automations.json) and restored on the next startup.
Schedule triggers default to persistent=True (the common case — "check
every morning" should survive a restart). Event triggers default to
persistent=False, and a predicate makes a trigger impossible to persist
at all: predicates are arbitrary Python callables and cannot be
serialized, so register_event_trigger(persistent=True, predicate=...)
raises rather than silently dropping the predicate on restore, which
would change the trigger's behavior without telling anyone.
"""

import dataclasses
import time
import uuid


def _jsonable(result):
    if dataclasses.is_dataclass(result):
        return dataclasses.asdict(result)
    return result


class AutomationService:
    def __init__(self, events, executor, persistence=None):
        self.events = events
        self.executor = executor  # callable(action: dict) -> result
        self.persistence = persistence
        self.triggers = {}
        self._subscribed_events = set()
        if self.persistence is not None:
            self._load()

    # ---------------------------------------------------------
    # Persistence
    # ---------------------------------------------------------
    def _load(self):
        data = self.persistence.load_automations()
        for t in data.get("triggers", []):
            trigger_id = t["id"]
            if t["kind"] == "event":
                event_name = t["event_name"]
                self.triggers[trigger_id] = {
                    "id": trigger_id,
                    "kind": "event",
                    "event_name": event_name,
                    "predicate": None,  # predicates are never persisted
                    "action": t["action"],
                    "enabled": t.get("enabled", True),
                    "persistent": True,
                }
                if event_name not in self._subscribed_events:
                    self.events.on(
                        event_name,
                        lambda payload, en=event_name: self._handle_event(en, payload),
                    )
                    self._subscribed_events.add(event_name)
            elif t["kind"] == "schedule":
                self.triggers[trigger_id] = {
                    "id": trigger_id,
                    "kind": "schedule",
                    "interval_seconds": t["interval_seconds"],
                    "next_run": t["next_run"],
                    "action": t["action"],
                    "enabled": t.get("enabled", True),
                    "persistent": True,
                }

    def _save(self):
        if self.persistence is None:
            return
        persisted = []
        for t in self.triggers.values():
            if not t.get("persistent"):
                continue
            entry = {
                "id": t["id"],
                "kind": t["kind"],
                "action": t["action"],
                "enabled": t["enabled"],
            }
            if t["kind"] == "event":
                entry["event_name"] = t["event_name"]
            else:
                entry["interval_seconds"] = t["interval_seconds"]
                entry["next_run"] = t["next_run"]
            persisted.append(entry)
        self.persistence.save_automations({"triggers": persisted})

    # ---------------------------------------------------------
    # Registration
    # ---------------------------------------------------------
    def register_event_trigger(self, event_name, action, predicate=None,
                                trigger_id=None, persistent=False):
        if persistent and predicate is not None:
            raise ValueError(
                "Event triggers with a predicate cannot be persistent — "
                "predicates are Python callables and aren't serializable. "
                "Register with persistent=False, or drop the predicate."
            )
        trigger_id = trigger_id or str(uuid.uuid4())
        self.triggers[trigger_id] = {
            "id": trigger_id,
            "kind": "event",
            "event_name": event_name,
            "predicate": predicate,
            "action": action,
            "enabled": True,
            "persistent": persistent,
        }
        if event_name not in self._subscribed_events:
            self.events.on(event_name, lambda payload: self._handle_event(event_name, payload))
            self._subscribed_events.add(event_name)
        self._save()
        return trigger_id

    def register_schedule_trigger(self, interval_seconds, action, trigger_id=None,
                                   run_immediately=False, persistent=True):
        trigger_id = trigger_id or str(uuid.uuid4())
        next_run = time.time() if run_immediately else time.time() + interval_seconds
        self.triggers[trigger_id] = {
            "id": trigger_id,
            "kind": "schedule",
            "interval_seconds": interval_seconds,
            "next_run": next_run,
            "action": action,
            "enabled": True,
            "persistent": persistent,
        }
        self._save()
        return trigger_id

    def unregister(self, trigger_id):
        self.triggers.pop(trigger_id, None)
        self._save()

    def set_enabled(self, trigger_id, enabled):
        if trigger_id in self.triggers:
            self.triggers[trigger_id]["enabled"] = enabled
            self._save()

    def list_triggers(self):
        """Omits action/predicate (not JSON-safe/stable) — this is a status
        view, not a way to recover the registered callables."""
        return [
            {k: v for k, v in t.items() if k not in ("action", "predicate")}
            for t in self.triggers.values()
        ]

    # ---------------------------------------------------------
    # Firing
    # ---------------------------------------------------------
    def _handle_event(self, event_name, payload):
        for trigger in list(self.triggers.values()):
            if not trigger["enabled"] or trigger["kind"] != "event":
                continue
            if trigger["event_name"] != event_name:
                continue
            if trigger["predicate"] is not None and not trigger["predicate"](payload):
                continue
            self._fire(trigger, payload or {})

    def tick(self, now=None):
        """Checks schedule-based triggers and fires any that are due.
        Returns the list of trigger IDs that fired. Persists updated
        next_run values for persistent triggers, but only when something
        actually fired — this is expected to be called frequently by
        AssistantCore.start_automation_ticker(), so a no-op tick should
        stay cheap and not touch disk."""
        now = now if now is not None else time.time()
        fired = []
        for trigger in list(self.triggers.values()):
            if not trigger["enabled"] or trigger["kind"] != "schedule":
                continue
            if trigger["next_run"] > now:
                continue
            self._fire(trigger, {"scheduled_at": trigger["next_run"]})
            fired.append(trigger["id"])
            trigger["next_run"] = now + trigger["interval_seconds"]
        if fired:
            self._save()
        return fired

    def _fire(self, trigger, context):
        self.events.emit("automation.triggered", {"trigger_id": trigger["id"], "context": context})
        try:
            result = self.executor(trigger["action"])
            self.events.emit("automation.completed", {
                "trigger_id": trigger["id"],
                "result": _jsonable(result),
            })
        except Exception as exc:
            self.events.emit("automation.failed", {
                "trigger_id": trigger["id"],
                "error": str(exc),
            })
