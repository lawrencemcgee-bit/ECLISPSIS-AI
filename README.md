# ECLIPSIS-AI

A personal assistant, re-engineered from an earlier stalled codebase
through a disciplined, phase-by-phase roadmap, now with a second UI
built in Flet and real (optional, offline, free) voice I/O layered on
top of the original architecture.

**Roadmap status: Milestones 0–13 complete.** The architecture — event
bus, agents, memory, permissions, observability, automation, a
cross-platform API — is built and tested. Two pieces of post-roadmap work
are in progress on top of it: a Flet-based UI (replacing PySide6/QML) and
real speech-to-text/text-to-speech. See
[Current Capabilities](#current-capabilities) for exactly what's real
versus what's still a stub, and **Recent Updates** below for what's
changed most recently — this section is kept current as work happens,
not just at milestone boundaries.

## Recent Updates

- **Fixed a native crash in the test suite.** Running the full suite on
  a machine with working audio hardware opened and tore down several real
  PortAudio streams back-to-back across different tests, crashing the
  interpreter (Windows access violation, `0xC0000005`). The test suite
  now forces simulated audio/voice unconditionally
  (`ECLIPSIS_FORCE_SIMULATED_AUDIO`/`_VOICE` env vars, set at the top of
  `test_all_phases.py`) — tests must never depend on or exercise real
  hardware, independent of what specifically caused this crash. The
  real-capture callback in `AudioService` was also hardened against
  exceptions crossing the native callback boundary, a separate known
  crash class for ctypes/cffi-based audio bindings.
- **Fixed a stale test assertion.** `test_diagnostics_snapshot_shape`
  hardcoded `voice`/`audio` as always-simulated — true when it was
  written (Milestone 9), no longer true once real capture/STT became
  possible. Now checks that the `"simulated"` flag correctly mirrors
  actual availability instead of asserting a fixed value.
- **Real voice I/O added**: real mic capture (`sounddevice`), real STT
  (`vosk`, offline/free), real TTS (`pyttsx3`, offline/free) — all
  optional at runtime with graceful fallback to the original simulated
  behavior. Wired into Nova's mic button end-to-end. See
  `docs/voice_io_assessment.md`.
- **Flet UI added** (`src/ui_flet/`, `flet_run.py`) as a proposed
  replacement for PySide6/QML — two persona designs (Nova, committed to;
  Lyra, a lighter unmaintained skeleton). `src/ui/` (QML) is untouched.
  See `docs/flet_migration_assessment.md`.

## Getting Started

```bash
pip install -r requirements.txt
```

**Flet UI — Nova** (requires `flet`; this is the actively developed UI):
```bash
python flet_run.py --persona nova
python flet_run.py --persona nova --web   # in a browser instead of a native window
```

**Desktop UI — QML** (requires PySide6; original UI, still intact but no
longer the active development target):
```bash
python run.py
```

**HTTP API** (requires fastapi/uvicorn):
```bash
uvicorn api:app --reload
# or: make start-api
```

All three entry points construct one shared `AssistantCore` instance and
are safe to run independently or side by side.

**For real voice I/O** (optional — everything works without this, just
with simulated audio/no real speech):
```bash
pip install vosk pyttsx3
# + download a Vosk model — see docs/voice_io_assessment.md §3
```

## Testing

```bash
python test_all_phases.py
```

Plain `unittest`, standard library only for most of the suite — no
installs required beyond what's already in `requirements.txt`. Covers
Phases 1–13 plus post-roadmap work. Tests requiring an optional
dependency that isn't installed (PySide6, fastapi/httpx) skip cleanly
rather than failing. The suite forces simulated audio/voice
unconditionally, regardless of what's installed on the machine running
it — see Recent Updates above. Run a single phase with:
```bash
python -m unittest test_all_phases.Phase9Observability -v
```

## Current Capabilities

| Subsystem | Status |
|---|---|
| Conversation / message processing | Real |
| Agents (OneNote, Weather, News) | Real |
| Memory (short + long-term) | Real, persists across restarts |
| Plugins | Real (discovery, enable/disable, execution) |
| Permissions & safety policy | Real — fails closed by default, decisions persist |
| Observability (metrics, diagnostics, health) | Real |
| Automation (event & schedule triggers) | Real — persists, ticked by a background thread |
| Cross-platform HTTP API | Real for the above; explicit `501`s for capabilities that don't exist yet (see below) |
| Flet UI (Nova) | Real — chat, agent tray, mic/camera, reactive orb; window-restore-across-restart not yet confirmed |
| QML UI | Real, but no longer the active development target |
| Voice (STT/TTS/mic capture) | **Real when installed** (`vosk`/`pyttsx3`/`sounddevice` + a Vosk model) — falls back to simulated/no-op otherwise. Neither path has been machine-verified beyond a smoke test |
| Vision | Wired correctly through permissions; camera capture itself is still a **placeholder**, no real pipeline |
| NCI (content analysis/scoring) | Returns input text back — **no real scoring model yet** |
| Coding / social-media / browser agents | **Do not exist yet** |
| Creative-content generation | **Does not exist yet** |

## Project Structure

```
src/agents/    — OneNote, Weather, News agents + registry
src/api/       — FastAPI app factory
src/core/      — AssistantCore + all core services (event bus, memory,
                 permissions, verification, safety rules, observability,
                 automation, persistence, tasks, tools, state, logging)
src/engine/    — Message-processing backend
src/plugins/   — Plugin manager + example plugin
src/services/  — Domain services: audio, vision, voice, nci, research,
                 weather, news, onenote
src/ui/        — QML desktop UI + PySide6 state bridge (original, intact)
src/ui_flet/   — Flet UI: shared bridge + Nova/Lyra personas
config/        — Settings (not currently wired up — see architecture doc)
docs/          — Architecture baseline, migration/voice assessments, and
                 a Before/After report per milestone
data/          — Runtime JSON persistence (created on first run)
models/        — Vosk STT model goes here (not included — see voice doc)
api.py         — HTTP API entry point (`uvicorn api:app`)
run.py         — QML desktop UI entry point
flet_run.py    — Flet UI entry point (`--persona nova|lyra`, `--web`)
test_all_phases.py — The regression suite
```

## Documentation

- [`docs/architecture_baseline.md`](docs/architecture_baseline.md) — the
  current, accurate state of the repository: full module inventory,
  per-subsystem status, concurrency model, known orphaned/dead code, and
  what's next.
- [`docs/flet_migration_assessment.md`](docs/flet_migration_assessment.md)
  — the Flet UI design/build: confidence levels, architecture, and a
  Flet concepts tutorial.
- [`docs/voice_io_assessment.md`](docs/voice_io_assessment.md) — real
  voice I/O: what's built, setup (including the Vosk model download),
  and testing steps.
- `docs/milestone_N_report.md` — a Before/After report for each milestone
  from Phase 9 onward, documenting exactly what changed, why, and what
  was deliberately left out of scope.

## Roadmap

| Phase | Milestone | Status |
|---|---|---|
| 0 | Discovery & Baseline | Done |
| 1 | Stabilization | Done |
| 2 | Core Runtime & Event Bus | Done |
| 3 | Agent & Tool Architecture | Done |
| 4 | Assistant Core & Orchestration | Done |
| 5 | Memory System | Done |
| 6 | Multimodal System | Done |
| 7 | Voice System | Done |
| 8 | NCI Analytics | Done |
| 9 | Observability & Operations Center | Done |
| 10 | Security & Permissions | Done |
| 11 | Cross-Platform API | Done |
| 12 | Automation & Proactive Assistance | Done |
| 13 | Final Validation | Done |

**Post-roadmap work in progress** (not part of the original 14 phases):
Flet UI migration (Nova built and smoke-tested; Lyra a lighter unmaintained
skeleton), real voice I/O (built, not yet machine-verified end-to-end).
Still fully unbuilt: real NCI scoring, a real vision pipeline, new agents
(coding/social-media/browser), a creative-content layer. See
`docs/architecture_baseline.md` §11–12 for the full known-limitations list.
