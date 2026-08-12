# ECLIPSIS-AI — Architecture Baseline
Refreshed at Milestone 13 (Final Validation) — supersedes the Milestone 0
version of this document, which described a pre-scaffolding, empty
repository. That was accurate at the time; it has been stale since
Milestone 1. This refresh reflects the actual current state.

**Tier 2 repo-hygiene update**: `src/ui/` (QML/PySide6) is now formally
**deprecated** — kept as a fallback, no further work planned. See
`src/ui/DEPRECATED.md`. Of the five files originally flagged as orphaned
in §9 below, four were confirmed unreferenced and deleted
(`src/core/persistence.py`, `src/ui/tk_stabilization.py`,
`config/config_manager.py`, `config/settings.yaml`). The fifth,
`src/ui/plugin_panel.qml`, turned out to still be live-wired into
`main_window.qml`'s Plugins toggle button — the original orphaned-file
assessment was wrong about that one — so it was restored rather than
deleted. §9 is left below as a historical record of what was found and
why, with that correction noted inline.

**Tier 3 update**: `NCIService` and `VisionService` are no longer
placeholder-level, and real `CodingAgent`/`SocialAgent` have been added
(a browser agent was deliberately deferred) — see §7.

## 1. Overview
14-phase roadmap (0–13), all phases now have working code and passing
tests. `AssistantCore` is the single orchestration point, shared by two
frontends: the desktop QML UI (`run.py` → `src/ui/qml_app.py`) and an HTTP
API (`api.py` → `src/api/api_app.py`). ~2,400 lines across `src/`.

**Important distinction**: this roadmap was about architecture and
plumbing — event bus, agents, memory, permissions, observability,
automation, a cross-platform API — not about the domain engines the
original product vision describes. Real voice I/O, real NCI scoring,
and a real vision pipeline have since been added on top of that
plumbing (Tier 3), along with real Coding, Social, and Creative-content
agents; a browser agent remains placeholder-level (deliberately
deferred). See §7 and §11.

## 2. Repository Structure
```
src/agents/       — OneNote, Weather, News, Coding, Social, Creative agents + registry
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
| AgentRouter + 6 agents (OneNote/Weather/News/Coding/Social/Creative) | Real, tested. Coding is local static analysis (ast/difflib) — never executes code, respecting SafetyRules' permanent `run_shell_command` block. Social is local post analysis — no posting/publishing (no OAuth/API-key infra in this codebase). Creative is template/procedural generation (headlines, writing prompts, outlines) plus heuristic critique (passive voice, cliches, filler words) — no LLM anywhere in this codebase, so generation is assembled from fixed templates, not composed prose; see creative_content_service.py's module docstring. |
| MemoryService | Real, tested (short + long-term, survives restart) |
| PersistenceService | Real — settings, chat history, memory, permissions, automations all persisted as JSON |
| VoiceService | Real STT (Vosk) + TTS (pyttsx3), confirmed working end-to-end — see `docs/voice_io_assessment.md`. Falls back to `simulate_command()` if the backend isn't available. |
| VisionService | Real camera capture (OpenCV) with graceful fallback to the original simulated placeholder — see `vision_service.py`. Analysis is local pixel-level signals (brightness, sharpness, dominant channel), not ML object/scene recognition. |
| AudioService | Simulated sine-wave samples, not real mic capture |
| NCIService | Real local heuristic scorer — see `nci_service.py`. Scores quality (depth, evidence density, readability, vocabulary) always, plus topic relevance when a topic is supplied. Accepts raw text or a fetched URL. No external LLM call. |
| ObservabilityService (Milestone 9) | Real — event-driven counters, last-error, system metrics |
| PermissionService / SafetyRules (Milestone 10) | Real — fail-closed by default, persisted grants |
| Cross-platform API (Milestone 11) | Real for existing capabilities, including `/social/analyze`, `/coding/analyze`, `/coding/diff` as of Tier 3; `501`s remain for nci/batch, nci/latest, vision/latest — no persisted-history/batch logic exists for those yet. Every route now requires an API key — see `ApiKeyService` below. |
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
deleted where it wasn't). **Update — Tier 2 repo-hygiene pass**: four of
these were confirmed unimported anywhere and deleted; the fifth
(`plugin_panel.qml`) was found to still be live-wired and restored
instead — see the correction inline below.
- `src/core/observability.py` — **fixed in Milestone 9** (was dead, now real; not part of this deletion)
- `src/core/persistence.py` — **deleted**. A separate, smaller, unused
  early draft of what `persistence_service.py` (the one actually used
  everywhere) became.
- `src/ui/plugin_panel.qml` — **initially flagged as a stale duplicate
  and deleted, then restored.** The original assessment ("Python code
  with a `.qml` extension ... never loaded") was wrong: `main_window.qml`
  actually loads it via a `Loader` (`pluginLoader`, source
  `"plugin_panel.qml"`) behind a visible "Plugins" toggle button. Deleting
  it would have silently broken that button in the QML fallback the first
  time someone clicked it. Kept as part of the deprecated QML tree.
- `src/ui/tk_stabilization.py` — **deleted**. A Milestone 1
  CustomTkinter placeholder from before the QML decision was made.
- `config/config_manager.py`, `config/settings.yaml` — **deleted**. Not
  imported anywhere in `src/`; the `config/` directory itself is now
  gone since it held only these two files.

Four of the five were not wired into any active code path, so deleting
them does not affect runtime behavior; the fifth was wired in and is
kept. Confirmed via `grep` across `src/`, `run.py`, `api.py`, and
`flet_run.py` before removal, and via a full `test_all_phases.py` run
afterward (72 passed / 7 skipped, same skip count as before).

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
- Domain engines that remain placeholder-level: a browser agent
  (fetch-and-read a URL) — deliberately deferred, not built. Everything
  else from the original re-engineering prompt's domain-engine list
  (real voice I/O, real NCI scoring, a real vision pipeline, real
  Coding/Social/Creative agents) has shipped in Tier 3; see §7.
- ~~No auth on the HTTP API~~ — fixed in Tier 3. Every route requires an
  `X-API-Key` header (src/api/api_key_service.py); a bootstrap key is
  generated and printed to stderr on first run, `/auth/keys` manages
  additional keys, and a full lockout self-heals on the next restart.
- Four of the five orphaned files formerly in §9 have been deleted
  (Tier 2); the fifth (`plugin_panel.qml`) was restored — see §9.
- `src/ui/` (QML/PySide6) is now deprecated — see `src/ui/DEPRECATED.md`.
- ~~`AutomationService` actions are limited to `notify`/`message`/`agent`/
  `plugin`~~ — fixed in Tier 3. A `sequence` action type runs a list of
  steps in order (each step any other action type, including another
  sequence, bounded by `AssistantCore.MAX_SEQUENCE_DEPTH`/
  `MAX_SEQUENCE_STEPS`); `stop_on_error` (default `True`) controls
  whether a failing step halts the rest. See
  `AssistantCore._execute_sequence_action`.
- `/nci/batch`, `/nci/latest`, `/vision/latest` remain `501` — batch
  scoring and persisted history have no backing implementation yet, even
  though single-shot NCI scoring and vision capture are now real.
- No browser agent (URL fetch-and-read) — deliberately skipped when
  Coding/Social/Creative agents were built; the NCI service already does
  URL fetching internally (`_fetch_url`) but there's no standalone agent
  exposing that as a general-purpose capability.
- Creative-content generation is template/procedural (fixed headline
  templates, curated writing-prompt word lists, fixed outline
  structures per content type), not composed prose — there's no LLM
  anywhere in this codebase, by design. See
  `creative_content_service.py`'s module docstring.
- No HTTP API endpoints exist yet for registering/listing/managing
  automations (`register_schedule_automation` etc. are AssistantCore
  methods, callable in-process from QML/Flet, but not exposed over
  `/automations/*`) — pre-existing gap, not introduced by the
  `sequence` action type, but worth flagging since automation is
  otherwise now fully HTTP-API-authenticated territory (§7).
- Flet packaging (`flet build`) is configured but not actually
  compiled anywhere in this repo's history — see `docs/flet_packaging.md`.
  Two dedicated entry points (`nova_main.py`, `lyra_main.py`) exist and
  the exact `flet build` commands were verified to parse/initialize
  correctly, but the real compile needs a Flutter SDK download this
  project's dev/CI sandbox couldn't reach (network-egress restriction
  specific to that environment, not a config problem — see the doc for
  what was actually verified vs. what a normal machine still needs to
  run). No built artifact ships in this repo; running the documented
  commands on a machine with normal internet access is still required.

## 12. Next Steps
The original 14-phase roadmap (Milestones 0–13) is complete, the Tier 2
repo-hygiene pass is done, and Lyra has been brought to feature parity
with Nova. Tier 3 has shipped real NCI scoring, a real vision pipeline,
real Coding/Social/Creative agents (`coding_service.py`,
`ast`/`difflib`-based, no execution; `social_content_service.py`, local
post analysis, no posting; `creative_content_service.py`,
template/procedural generation + heuristic critique, no LLM), API-key
auth on the HTTP API (`api_key_service.py`), multi-step (`sequence`)
automation actions, and Flet packaging configuration (`nova_main.py`,
`lyra_main.py`, `docs/flet_packaging.md` — commands verified to parse
and initialize correctly; the actual compile still needs to run on a
machine that can reach the Flutter SDK, since this project's sandbox
couldn't). What remains: a browser agent, HTTP endpoints for automation
management, the batch/persistence-backed NCI and vision endpoints
(`/nci/batch`, `/nci/latest`, `/vision/latest`), and actually running
the Flet build commands on a real machine to confirm they produce a
working artifact end-to-end. These don't have phase numbers yet — worth
a fresh planning pass to sequence them.
