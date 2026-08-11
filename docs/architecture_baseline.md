# ECLIPSIS-AI — Architecture Baseline
Refreshed at Milestone 13 (Final Validation) — supersedes the Milestone 0
version of this document, which described a pre-scaffolding, empty
repository. That was accurate at the time; it has been stale since
Milestone 1. This refresh reflects the actual current state.

**Tier 2 repo-hygiene update**: `src/ui/` (QML/PySide6) is now formally
**deprecated** — kept as a fallback, no further work planned. See
`src/ui/DEPRECATED.md`. The five orphaned files flagged in §9 below have
been deleted (`src/core/persistence.py`, `src/ui/plugin_panel.qml`,
`src/ui/tk_stabilization.py`, `config/config_manager.py`,
`config/settings.yaml`); §9 is left below as a historical record of what
was found and why each was safe to remove, rather than rewritten away.

## 1. Overview
14-phase roadmap (0–13), all phases now have working code and passing
tests. `AssistantCore` is the single orchestration point, shared by two
frontends: the desktop QML UI (`run.py` → `src/ui/qml_app.py`) and an HTTP
API (`api.py` → `src/api/api_app.py`). ~2,400 lines across `src/`.

**Important distinction**: this roadmap was about architecture and
plumbing — event bus, agents, memory, permissions, observability,
automation, a cross-platform API — not about the domain engines the
original product vision describes. Several of those (real NCI scoring,
a real vision pipeline, real STT/TTS, coding/social/browser agents, a
creative-content layer) remain placeholder-level. See §7 and §11.

## 2. Repository Structure
```
src/agents/       — OneNote, Weather, News agents + registry
src/api/          — FastAPI app factory (Phase 11)
src/core/         — AssistantCore + all core services (event bus, memory,
                     permissions, verification, safety rules, observability,
                     automation, persistence, tasks, tools, state, logging)
src/engine/       — LocalEngine (message processing backend)
src/plugins/      — Plugin manager + one example plugin
src/services/     — Domain services: audio, vision, voice, nci, research,
                     weather, news, onenote
src/tests/        — Small pytest-style smoke tests (separate from the
                     main suite — see §10)
src/ui/           — QML desktop UI + PySide6 state bridge
config/           — settings.yaml, config_manager.py (see §11 — unused)
docs/             — this file + per-milestone Before/After reports
data/             — runtime JSON persistence (created at first run)
api.py, run.py    — process entry points
test_all_phases.py — the actual regression suite (Phases 1–13, unittest,
                     stdlib only + optional psutil/fastapi for full coverage)
```

## 3. Entry Points
- `run.py` → `run_qml_ui(assistant)` — desktop UI, requires PySide6
- `api.py` → module-level `app` for `uvicorn api:app` — HTTP API, requires
  fastapi/uvicorn (this file didn't exist before Milestone 11; the
  Makefile's `start-api` target referenced it with nothing behind it)
- Both construct exactly one `AssistantCore` and call
  `start_automation_ticker()` (Milestone 13) so schedule-based automations
  actually run in either process.

## 4. Runtime Configuration
`config/settings.yaml` and `config/config_manager.py` exist but are not
imported anywhere in `src/` — see §11. Actual runtime settings live in
`data/settings.json`, written by `AssistantCore`/`PersistenceService`
directly.

## 5. Dependency Manifest
`pyproject.toml` and `requirements.txt` are now consistent with each
other (they'd drifted — `psutil` and `fastapi`/`uvicorn` were added to
one but not both during Milestones 9 and 11; fixed at each point). Several
declared dependencies (`pydantic`, `tinydb`, `loguru`) are still not
actually imported anywhere in `src/` — the codebase has stayed
stdlib-only by choice through Milestone 12; `pydantic` became genuinely
used starting Milestone 11 (request/response models in `src/api/api_app.py`).

## 6. UI Inventory
`src/ui/qml_app.py` (PySide6 bootstrap) + `src/ui/state_bridge.py`
(Python↔QML bridge) + QML files under `src/ui/*.qml`. One exception:
`src/ui/plugin_panel.qml` is not actually QML — see §9.

## 7. Engine, Agent, Voice, Vision, NCI, Persistence
| Subsystem | Status |
|---|---|
| LocalEngine / ConversationService | Real, tested |
| AgentRouter + 3 agents (OneNote/Weather/News) | Real, tested |
| MemoryService | Real, tested (short + long-term, survives restart) |
| PersistenceService | Real — settings, chat history, memory, permissions, automations all persisted as JSON |
| VoiceService | State machine is real; STT/TTS are not — `simulate_command()` |
| VisionService | Constructed and wired correctly; `capture()` is a placeholder string, no real camera/pipeline |
| AudioService | Simulated sine-wave samples, not real mic capture |
| NCIService | `analyze()`/`interpret()` returns `{"interpreted": text}` — no real scoring model |
| ObservabilityService (Milestone 9) | Real — event-driven counters, last-error, system metrics |
| PermissionService / SafetyRules (Milestone 10) | Real — fail-closed by default, persisted grants |
| Cross-platform API (Milestone 11) | Real for existing capabilities; `501`s for nci/batch, nci/latest, vision/latest, social/analyze — no backing logic exists for those yet |
| AutomationService (Milestones 12–13) | Real — event/schedule triggers, persisted, ticked by a background thread in both entry points |

## 8. Concurrency & UI Thread Safety
Everything through Milestone 12 was synchronous, single-threaded, and
deterministic (a deliberate choice — see `AutomationService`'s docstring).
Milestone 13 introduces the one background thread in the codebase:
`AssistantCore.start_automation_ticker()`, a daemon thread calling
`automation_tick()` on an interval. It touches `AutomationService.triggers`
and calls back into `AssistantCore`/other services on that thread, not the
Qt main thread — fine for the current action types (`notify`, `message`,
`agent`, `plugin`, all plain Python), but worth remembering if a future
action type ever needs to touch a Qt widget directly, which must happen on
the main thread.

## 9. Integrity Findings
Confirmed and fixed during hands-on verification (the user ran `python
run.py` for the first time in this whole engagement and reported the
actual failure):
- **Every `.qml` file used Qt5-style versioned imports**
  (`import QtQuick 2.15`, `import QtQuick.Layouts 1.15`, etc.) — a
  leftover from before this project was ported to PySide6/Qt6. Qt6 kept
  backward-compatible handling for the core modules (`QtQuick`,
  `QtQuick.Controls`, `QtQuick.Window`, `QtQuick.Layouts`), so those
  loaded despite the stale version numbers. `QtMultimedia` was
  substantially rewritten in Qt6 and has no such compatibility shim, so
  `import QtMultimedia 5.15` failed outright with "module not installed"
  — a misleading error, since the module was actually present; it just
  didn't have a "5.15" to serve. **Fixed**: every import across all 17
  `.qml` files switched to Qt6's recommended unversioned form
  (`import QtQuick`, `import QtMultimedia`, etc.).
- That fix alone wasn't sufficient: `main_window.qml` also had a
  top-level `import QtMultimedia` it never actually needed — every use
  went through `soundLoader.item.playClick()` etc., against a `Loader`
  that only needs the module inside `sound_engine.qml`. Because QML
  resolves a file's imports at parse time for the whole file, that one
  unused import meant the *entire window* failed to load if
  `QtMultimedia` couldn't resolve for any reason, even though the actual
  usage was already safely isolated behind a `Loader`. **Fixed**: removed
  the import from `main_window.qml`; added a `playSound(name)` helper
  that no-ops if `soundLoader.item` is null, and an `onStatusChanged`
  handler that logs a warning instead of failing silently. If
  `QtMultimedia` genuinely can't load on a given machine, sound effects
  are now disabled instead of the whole app being unusable.

Confirmed orphaned/unused code, found while working through Milestones
9–13 (fixed where fixing was in scope; flagged rather than silently
deleted where it wasn't). **Update — deleted in the Tier 2 repo-hygiene
pass**, since none were imported anywhere and each had a confirmed,
understood reason for existing:
- `src/core/observability.py` — **fixed in Milestone 9** (was dead, now real; not part of this deletion)
- `src/core/persistence.py` — **deleted**. A separate, smaller, unused
  early draft of what `persistence_service.py` (the one actually used
  everywhere) became.
- `src/ui/plugin_panel.qml` — **deleted**. Python code with a `.qml`
  extension; a stale duplicate of an early `assistant_core.py` missing
  everything from Milestone 6 onward. Harmless (invalid QML, never
  loaded) but confusing. Flagged in the Milestone 10 report.
- `src/ui/tk_stabilization.py` — **deleted**. A Milestone 1
  CustomTkinter placeholder from before the QML decision was made.
- `config/config_manager.py`, `config/settings.yaml` — **deleted**. Not
  imported anywhere in `src/`; the `config/` directory itself is now
  gone since it held only these two files.

None of these were wired into any active code path, so deleting them
does not affect runtime behavior. Confirmed via `grep` across `src/`,
`run.py`, `api.py`, and `flet_run.py` before removal, and via a full
`test_all_phases.py` run afterward (still 77 tests, same pass/skip
counts).

## 10. Tests, Static Analysis, CI
- **`test_all_phases.py`** is the actual regression suite — plain
  `unittest`, no installs required beyond the standard library for most of
  it. As of Milestone 13: 67 tests, all passing or cleanly skipped when an
  optional dependency (PySide6, fastapi/httpx) isn't installed in the
  environment running it.
- `src/tests/test_engine.py` and `src/tests/test_results.py` are small,
  legitimate pytest-style smoke tests predating `test_all_phases.py`.
  They use plain `assert` functions, not `unittest.TestCase`, so
  `python -m unittest discover` finds zero tests in that directory —
  they need `pytest` (the Makefile's `test:` target already expects
  this). Not dead code, just a second, older, narrower test suite.
- No CI configuration (`.github/workflows/`, etc.) exists in this
  repository.
- `ruff`/`mypy` are declared dev dependencies; no config files
  (`ruff.toml`, `mypy.ini`) were found, so both would run with defaults.

## 11. Known Limitations
- Domain engines remain placeholder-level: real NCI scoring and a real
  vision pipeline, and the coding/social-media/browser agents and
  creative-content layer described in the original re-engineering
  prompt, were never part of this 14-phase roadmap and remain unbuilt.
  (Real voice I/O — STT/TTS — is no longer on this list; confirmed
  working end-to-end, see `docs/voice_io_assessment.md`.)
- No auth on the HTTP API (Milestone 11's known limitation, unchanged).
- The five orphaned files formerly in §9 have been deleted (Tier 2).
- `src/ui/` (QML/PySide6) is now deprecated — see `src/ui/DEPRECATED.md`.
- `AutomationService` actions are limited to `notify`/`message`/`agent`/
  `plugin` — no way yet to, say, run a multi-step automation.
- Lyra (the second Flet persona) is a lighter skeleton than Nova — no
  pulse loop, no waveform, default chat builder — and isn't currently
  being brought to parity.

## 12. Next Steps
The original 14-phase roadmap (Milestones 0–13) is complete, and the
Tier 2 repo-hygiene pass (QML deprecation, orphaned-file removal) is
done. What remains is the domain-engine work that roadmap was always
scoped around, not through: real NCI scoring, a real vision pipeline,
new agents (coding, social-media, browser), the creative-content layer,
API authentication, multi-step automations, and Lyra parity. These
don't have phase numbers yet — worth a fresh planning pass to sequence
them.
