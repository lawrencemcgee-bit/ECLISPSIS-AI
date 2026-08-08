# Milestone 13 Report — Final Validation

## 1. Summary
Milestone 13 closes out the original 14-phase roadmap (Milestones 0–13).
It resolves the two things Milestone 12 deliberately left open — nothing
was calling `tick()`, and triggers didn't survive a restart — and does a
full documentation/integrity pass across the whole repository rather than
just this milestone's own changes, since "Final Validation" is the point
where that's supposed to happen.

## 2. Before
- `AutomationService.tick()` existed and was fully tested in isolation,
  but nothing in `run.py`, `qml_app.py`, or `api.py` ever called it — in a
  real running process, schedule-based triggers were inert.
- Automation triggers were in-memory only. Restarting the app lost every
  registered trigger, including ones that conceptually should survive
  (a recurring "check every morning" automation).
- `docs/architecture_baseline.md` still described "a repository
  containing only a README.md" — accurate at Milestone 0, stale since
  Milestone 1, never revisited since.

## 3. After

**Tick wiring** — `AssistantCore.start_automation_ticker(interval_seconds=30)`
starts a daemon background thread calling `automation_tick()` on an
interval; `stop_automation_ticker()` stops it cleanly. This is a plain
`threading.Thread`, not a Qt `QTimer` or an asyncio task, specifically
because `AssistantCore` is shared between two different process types
(`qml_app.py`'s Qt event loop, `api.py`'s uvicorn/ASGI loop) and
shouldn't assume which one is hosting it. Both entry points now call
`assistant.start_automation_ticker()` once at startup; `qml_app.py` also
calls `stop_automation_ticker()` after `app.exec()` returns, before exit.

**Persistence decision** — every trigger is registered with an explicit
`persistent` flag:
- Schedule triggers default `persistent=True` (the common case — a
  recurring check should survive a restart)
- Event triggers default `persistent=False`
- A trigger with a `predicate` **cannot** be persistent —
  `register_event_automation(persistent=True, predicate=...)` raises
  `ValueError` rather than silently dropping the predicate on restore,
  which would change what the trigger actually does without telling
  anyone. Predicates are Python callables; they cannot be serialized.

Persisted triggers are written to `data/automations.json` via two new
`PersistenceService` methods (`load_automations()`/`save_automations()`),
following the exact pattern Milestones 9 and 10 already established for
settings/permissions.

**Documentation** — `docs/architecture_baseline.md` was fully rewritten
to describe the actual current repository: module inventory, per-subsystem
status table (what's real vs. still placeholder — see §7 there), the
concurrency model (now including the one background thread this milestone
introduced), and, honestly, a list of five files found to be orphaned/dead
code during Milestones 9–13 that were flagged but intentionally not
deleted without being asked (§9 of that doc).

## 4. Files Changed
- `src/core/automation_service.py` — persistence support added
  (`_load()`/`_save()`, `persistent` flag on both trigger kinds)
- `src/core/assistant_core.py` — passes `self.persistence` into
  `AutomationService`; adds `start_automation_ticker()` /
  `stop_automation_ticker()`
- `src/core/persistence_service.py` — added `load_automations()` /
  `save_automations()`
- `src/ui/qml_app.py` — calls `start_automation_ticker()` /
  `stop_automation_ticker()`
- `api.py` — calls `start_automation_ticker()`
- `test_all_phases.py` — new `Phase13FinalValidation` (8 tests)
- `docs/architecture_baseline.md` — fully rewritten

## 5. Checks Run & Results
`python test_all_phases.py`: **67 tests, 60 passed, 7 skipped** (1
pre-existing PySide6 skip + 6 pre-existing Phase 11 fastapi/httpx skips —
same environment gaps flagged since Milestones 9 and 11, nothing new).

New tests cover: a persistent schedule trigger surviving a simulated
restart, a non-persistent one correctly not surviving, a persistent event
trigger surviving *and* still firing correctly after restart, the
predicate+persistent combination raising `ValueError`, the ticker actually
calling `tick()` on its own (a genuine timing test — short interval, small
sleep, generous assertion), the ticker being idempotent (a second
`start_automation_ticker()` call stops the first thread rather than
stacking threads), a regression guard that `architecture_baseline.md`
no longer contains the Milestone-0 "repository currently contains only a
README" line, and a check that every milestone report from 9–13 actually
exists on disk.

## 6. Behavior Preserved
Every Milestone 12 test still passes as-is — `persistent` defaults
preserve prior test behavior without any test needing to change (schedule
triggers already behaved as if persistent; they just weren't actually
saved to disk before). No existing method's required arguments changed.

## 7. Known Limitations (roadmap-wide, not just this milestone)
Carried forward from `docs/architecture_baseline.md`, since this is the
final phase and these don't disappear just because the roadmap ends here:
- Domain engines are still placeholder-level: real NCI scoring, a real
  vision pipeline, real STT/TTS, and the coding/social-media/browser
  agents and creative-content layer from the original re-engineering
  prompt were never part of this 14-phase roadmap and remain unbuilt.
- No auth on the HTTP API.
- Five orphaned files remain in the repository (§9 of the architecture
  baseline) — flagged across three milestones now, never silently
  removed, still awaiting an explicit go-ahead.
- Automation actions are limited to `notify`/`message`/`agent`/`plugin` —
  no multi-step automations yet.

## 8. Roadmap Status
**Milestones 0–13 are complete.** Every phase has working, tested code;
`test_all_phases.py` covers all of them in one runnable suite. This is
the end of the roadmap that was scoped in the original re-engineering
prompt — it is not the end of the product. The domain-engine work in §7
above was always separate from this roadmap's architecture-and-plumbing
scope, and is the natural next thing to plan, now that there's a solid,
observable, permissioned, automatable core to build it on top of.
