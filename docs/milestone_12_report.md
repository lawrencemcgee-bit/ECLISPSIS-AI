# Milestone 12 Report — Automation & Proactive Assistance

## 1. Summary
Milestone 12 added `AutomationService`: event- and schedule-based triggers
that let the assistant act without a message being sent first. Nothing
like this existed anywhere in the codebase — this is new capability, not
a fix to something broken. It's deliberately not a background scheduler;
it fires on `tick()`, which something else calls (a future UI timer, a
daemon thread, or a test) — keeping every trigger's timing deterministic
and testable without real wall-clock waits, the same reasoning that's
kept Vision/Voice/Audio simulated rather than reaching for real hardware.

## 2. Before
No automation, scheduling, or proactive-trigger concept existed anywhere
in `src/`. The assistant only ever acted in direct response to
`process_message()`, `capture_vision()`, or an explicit agent/plugin call.

## 3. After

**`src/core/automation_service.py`** — `AutomationService` supports two
trigger kinds:
- **Event triggers**: fire when a named event bus event occurs, with an
  optional predicate over the payload (e.g. only when `state.changed`'s
  `new` value is `"busy"`)
- **Schedule triggers**: fire when `tick()` is called and `next_run` has
  passed; recurring triggers reschedule themselves by `interval_seconds`

Actions are **declarative dicts, not arbitrary callables**:
```python
{"type": "notify", "text": "..."}                                    # surfaces a proactive suggestion
{"type": "message", "text": "..."}                                    # routes through process_message()
{"type": "agent", "agent": "weather", "kwargs": {"location": "..."}}  # routes through AgentRouter
{"type": "plugin", "plugin_id": "...", "payload": {...}}              # routes through PluginManager
```
This matters for the same reason Phase 10 exists: an automated trigger
can only do what a manual request could already do, through
`AssistantCore._execute_automation_action()` — it doesn't get its own,
less-guarded execution path. `AutomationService` itself never imports
`AssistantCore` (avoiding a circular import); it's handed the executor as
a callable.

`AssistantCore` gained: `register_event_automation()`,
`register_schedule_automation()`, `unregister_automation()`,
`set_automation_enabled()`, `list_automations()`, `automation_tick()`.

**Cross-phase integration**: `ObservabilityService` (Phase 9) now also
tracks `automation.completed`/`automation.failed` counters and captures
automation failures in `last_error`, exactly like it already does for
agent failures. `get_diagnostics()` gained an `"automation"` subsystem
entry (trigger count, enabled count).

## 4. Files Changed
- `src/core/automation_service.py` — new
- `src/core/assistant_core.py` — constructs `AutomationService`, adds
  `_execute_automation_action()` and the six wrapper methods above, adds
  `automation` to `get_diagnostics()`
- `src/core/observability.py` — subscribes to `automation.completed` /
  `automation.failed`
- `test_all_phases.py` — new `Phase12Automation` (9 tests)

## 5. Checks Run & Results
`python test_all_phases.py`: **59 tests, 52 passed, 7 skipped** (1
pre-existing PySide6 skip + 6 pre-existing Phase 11 skips — `fastapi`
still isn't installed in this sandbox; unrelated to this milestone).

New tests cover: event triggers firing on a real event
(`state.changed`) with a text-based notify action, predicate filtering,
schedule triggers firing/not-firing based on due time, recurring
triggers not double-firing immediately after rescheduling, disabled
triggers not firing, a real agent (`weather`) action executing
end-to-end, an unknown action type failing cleanly and being captured by
`ObservabilityService.last_error`, list/unregister, and the diagnostics
integration.

## 6. Behavior Preserved
No existing method changed signature or behavior. `AutomationService` is
purely additive — nothing else in the codebase calls into it yet, so
there was nothing to accidentally break.

## 7. Known Limitations
- **Nothing calls `tick()` yet.** No UI timer, no daemon thread — schedule
  triggers exist and are fully tested, but until something calls
  `automation_tick()` periodically (e.g. from `qml_app.py`'s event loop
  via a `QTimer`, or a background thread in `run.py`), they're inert in a
  running app. That wiring is a real UI-layer decision (how often to
  tick, on which thread) deliberately left for a dedicated pass rather
  than guessed at here.
- **Not exposed over the Phase 11 API.** Registering/listing automations
  is only reachable from Python right now, not HTTP. Unlike Phase 10's
  permission endpoints, this wasn't a strict necessity for anything else
  to function, so it was left out to keep this milestone scoped — worth
  adding once there's a real client that needs to configure automations
  remotely.
- No persistence: triggers are in-memory only and don't survive a
  restart (unlike permissions, settings, memory). Worth deciding whether
  that's actually desired — some proactive behavior (e.g. "check every
  morning") should probably survive restarts; some (e.g. a one-shot
  reminder from earlier in a session) probably shouldn't.
- No rate-limiting or dedup — a badly configured event trigger tied to a
  high-frequency event could fire very often. Not a problem yet since
  nothing registers triggers automatically, but worth guarding before
  anything does.

## 8. Next Milestone
Per the roadmap: Milestone 13 — Final Validation (full regression pass,
docs refresh, closing out the 14-phase roadmap). Given the Known
Limitations above, worth deciding before then whether `tick()` wiring and
trigger persistence belong inside Milestone 13's validation pass or as
their own follow-up.
