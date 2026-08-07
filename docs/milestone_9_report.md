# Milestone 9 Report — Observability & Operations Center

## 1. Summary
Milestone 9 replaced the orphaned, print-based `Observability` class with a
real `ObservabilityService`: event-driven counters, last-error tracking,
uptime, optional system metrics (CPU/RAM/disk via `psutil`, degrading
gracefully if unavailable), and a `get_diagnostics()` snapshot on
`AssistantCore` that reports per-subsystem health. This is the backend data
source the prompt's Diagnostics Panel / `GET /diagnostics` endpoint will
eventually read from — no UI or HTTP work was done in this milestone.

## 2. Before

`src/core/observability.py` defined an `Observability` class with `log()`
and `metric()` methods that printed to stdout. It was never imported by
`assistant_core.py`, any service, or any test — fully dead code. There was
no way to ask the running assistant "what's your current health?" beyond
reading the raw `logs/app.log` JSON lines by hand.

```python
class Observability:
    def log(self, message: str):
        print(f"[LOG] {message}")

    def metric(self, name: str, value):
        print(f"[METRIC] {name} = {value}")
```

## 3. After

`ObservabilityService` subscribes to the event bus at construction (before
any other subsystem is built, so no startup event is missed) and tracks:

- **Counters** — per event-type counts (`conversation.processed`,
  `agent.completed`, `agent.failed`, `plugin.toggle`,
  `nci.analysis.completed`, `state.<name>`)
- **last_error** — the most recent `conversation.error` or `agent.failed`
  payload, with a timestamp
- **uptime_seconds** — since the service was constructed
- **system_metrics()** — CPU/RAM/disk via `psutil`, returning
  `{"available": False}` if `psutil` isn't installed or a call fails,
  rather than raising

`AssistantCore.get_diagnostics()` is new. It builds a per-subsystem health
dict (engine, voice, vision, audio, plugins) — this stays in
`AssistantCore` rather than `ObservabilityService` because only
`AssistantCore` owns those subsystems and knows what "healthy" means for
each. Voice/vision/audio are explicitly flagged `"simulated": true` in the
output, since none of them talk to real hardware yet (Phase 6/7 placeholder
status, unchanged by this milestone) — a diagnostics panel should say so
honestly rather than reporting green health for a camera that was never
opened.

```python
def get_diagnostics(self):
    subsystems = {
        "engine": {"healthy": ..., "state": ...},
        "voice": {"healthy": True, "listening": ..., "simulated": True},
        "vision": {"healthy": True, "simulated": True},
        "audio": {"healthy": True, "active": ..., "simulated": True},
        "plugins": {"healthy": True, "loaded": ...},
    }
    return self.observability.snapshot(subsystems)
```

## 4. Files Changed
- `src/core/observability.py` — rewritten (was dead code)
- `src/core/assistant_core.py` — construct `ObservabilityService` first
  (right after `EventBus`), add `get_diagnostics()`
- `requirements.txt`, `pyproject.toml` — added `psutil` as an optional
  runtime dependency (handled gracefully if absent)
- `test_all_phases.py` — added `Phase9Observability` (6 tests); corrected
  the module docstring, which said "Covers Phases 1-5" while the suite had
  already grown to cover Phase 8

## 5. Checks Run & Results
Full suite: `python test_all_phases.py`
- 36 tests total (30 pre-existing + 6 new), all passing, 1 skip (PySide6
  not installed in this environment — pre-existing, unrelated to this
  milestone)
- New tests cover: construction/subscription order, counter increments on
  the normal message flow, `last_error` capture on agent failure,
  diagnostics snapshot shape, graceful degradation when `psutil` is
  unavailable, and engine health reflecting `AssistantState.ERROR`

## 6. Behavior Preserved
No existing event names, method signatures, or return shapes were changed.
`AssistantCore.__init__` gained one new attribute (`self.observability`)
and one new method (`get_diagnostics()`); nothing else in the constructor
or existing methods was altered.

## 7. Known Limitations
- `get_diagnostics()` is not yet exposed anywhere — no QML Diagnostics
  panel and no HTTP endpoint read from it. That's Phase 11 (Cross-Platform
  API) and a UI task, not part of this milestone.
- System metrics report host-machine CPU/RAM/disk, not per-subsystem
  resource usage (e.g., "how much CPU is the vision pipeline using") —
  that level of detail isn't meaningful yet since vision/voice are still
  simulated.
- `psutil` is a new dependency. It's optional at runtime (handled via
  try/except), but anyone running `pip install -r requirements.txt` or
  `uv sync` will pull it in.

## 8. Next Milestone
Proceed to Milestone 10 — Security & Permissions: replace
`PermissionService`'s auto-approve with a real approval flow, and expand
`SafetyRules` from a hardcoded blocklist into a configurable policy.
