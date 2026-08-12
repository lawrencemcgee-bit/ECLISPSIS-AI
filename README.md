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

- **Tier 1 (Nova completion) done**: window geometry now fully restores
  across a restart (position + maximized state, not just size — the
  latter was already working, the former two weren't); a voice settings
  panel (voice selection + speech rate, next to the permissions button);
  tool-tray icons flash on completion instead of giving no direct
  feedback; the orb now visually reacts while TTS is actually speaking
  (estimated from reply length, since precisely syncing to a background
  thread's completion would be a real thread-safety risk in Flet, not
  just unnecessary polish).
- **Real voice I/O confirmed working end-to-end, live, in Nova.** Mic
  capture → permission gate → Vosk STT → chat routing → pyttsx3 TTS,
  including a *second* voice command in the same session — the actual
  bug that needed chasing down. Three real, confirmed root causes found
  and fixed along the way, not guessed: (1) the Vosk model path was a
  bare relative path that resolved against the process's working
  directory rather than the repo root, so a model that existed on disk
  was silently never found; (2) `pyttsx3`'s TTS engine was being reused
  across background threads — a well-documented Windows SAPI5/COM issue
  where the first `speak()` call works and every later one silently does
  nothing; fixed by creating a fresh engine per call instead; (3) chat
  auto-scroll needed an explicit `scroll_to()` call, which turned out to
  be `async` in this Flet version — calling it synchronously silently
  no-op'd rather than erroring, caught via a `RuntimeWarning`. See
  `docs/voice_io_assessment.md` for the full account.
- **Added a real in-UI permissions panel to Nova** (a security-shield
  icon in a new header row). Grant/deny microphone and camera access
  proactively, rather than needing the one-off script from before.
  Deliberately proactive rather than a blocking "Allow?" popup at the
  moment of use: `PermissionService`'s decision handler is synchronous,
  but a Flet dialog's click is inherently async — blocking Flet's single
  event loop to wait for its own dialog's click would deadlock. Granting
  ahead of time sidesteps that entirely.
- **Confirmed real voice I/O is transcribing** — first real evidence
  (visible in logs) that the STT pipeline is actually working end-to-end
  on real hardware, not just passing unit tests against a fake recognizer.
- **Fixed mic state not syncing on launch.** `AssistantCore` restores
  the mic's previous on/off state from settings at startup, but the Flet
  bridge never reflected that in the mic button's visual state or
  restarted the waveform/voice-loop tasks that go with it — so a mic
  left on from a previous session looked off, and the first click
  actually turned it off instead of on. Also found `voice.listening`
  isn't persisted at all (only `audio.active` is), so a restored-active
  mic needed voice listening explicitly re-started too, not just checked.
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
| Cross-platform HTTP API | Real for the above; API-key auth on every route (`X-API-Key`, see `src/api/api_key_service.py`); explicit `501`s for capabilities that don't exist yet (see below) |
| Flet UI (Nova) | Real — chat, agent tray, mic/camera, reactive orb; window-restore-across-restart not yet confirmed |
| QML UI | Deprecated — kept as a fallback, no further work planned |
| Voice (STT/TTS/mic capture) | **Real, confirmed working end-to-end live in Nova** (`vosk`/`pyttsx3`/`sounddevice` + a Vosk model) — falls back to simulated/no-op if not installed |
| Vision | **Real camera capture** (OpenCV) with graceful fallback to simulated if unavailable — local pixel-level analysis (brightness, sharpness, dominant channel), not ML object/scene recognition |
| NCI (content analysis/scoring) | **Real local heuristic scorer** — quality (depth/evidence/readability/vocabulary) always, topic relevance when a topic is given; accepts raw text or a fetched URL |
| Coding agent | **Real local static analysis** (`ast`/`difflib`) — syntax, structure, docstring coverage, diffing; never executes code |
| Social-media agent | **Real local post analysis** — length vs. platform limits, hashtags/mentions/links, engagement heuristics; no posting/publishing (no OAuth infra) |
| Browser agent | Does not exist yet — deliberately deferred |
| Creative-content generation | **Real template/procedural generation** (headlines, writing prompts, outlines) + heuristic critique (passive voice, cliches, filler words) — no LLM anywhere in this codebase |

## Project Structure

```
src/agents/    — OneNote, Weather, News, Coding, Social, Creative agents + registry
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
Flet UI migration (Nova and Lyra both built and at feature parity),
real voice I/O (confirmed working end-to-end), real NCI scoring, a real
vision pipeline, real Coding/Social/Creative agents, and API-key auth on
the HTTP API — all shipped in Tier 3. Still unbuilt: a browser agent
(deliberately deferred), multi-step automations, and a few
batch/persistence-backed endpoints (`/nci/batch`, `/nci/latest`,
`/vision/latest`). See `docs/architecture_baseline.md` §11–12 for the
full known-limitations list.
