# ECLIPSIS-AI

A personal assistant desktop app (PySide6/QML), re-engineered from an
earlier stalled codebase through a disciplined, phase-by-phase roadmap.

**Roadmap status: Milestones 0–13 complete.** The architecture — event
bus, agents, memory, permissions, observability, automation, a
cross-platform API — is built and tested. The domain engines (real NCI
scoring, a real vision pipeline, real voice I/O, and several other
capabilities described in the original product vision) are **not**
part of this roadmap and remain unbuilt placeholders. See
[Current Capabilities](#current-capabilities) below for exactly what's
real versus what's still a stub.

## Getting Started

```bash
pip install -r requirements.txt
```

**Desktop UI** (requires PySide6):
```bash
python run.py
```

**HTTP API** (requires fastapi/uvicorn):
```bash
uvicorn api:app --reload
# or: make start-api
```

Both entry points construct one shared `AssistantCore` instance and are
safe to run independently or side by side.

## Testing

```bash
python test_all_phases.py
```

Plain `unittest`, standard library only for most of the suite — no
installs required beyond what's already in `requirements.txt`. Covers
Phases 1–13. Tests requiring an optional dependency that isn't installed
(PySide6, fastapi/httpx) skip cleanly rather than failing. Run a single
phase with:
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
| Voice | State machine is real; speech-to-text/text-to-speech are **not** — simulated |
| Vision | Wired correctly; camera capture is a **placeholder**, no real pipeline |
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
src/ui/        — QML desktop UI + PySide6 state bridge
config/        — Settings (not currently wired up — see architecture doc)
docs/          — Architecture baseline + a Before/After report per milestone
data/          — Runtime JSON persistence (created on first run)
api.py         — HTTP API entry point (`uvicorn api:app`)
run.py         — Desktop UI entry point
test_all_phases.py — The regression suite (Phases 1–13)
```

## Documentation

- [`docs/architecture_baseline.md`](docs/architecture_baseline.md) — the
  current, accurate state of the repository: full module inventory,
  per-subsystem status, concurrency model, known orphaned/dead code, and
  what's next.
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

The roadmap above covers architecture and plumbing. Real NCI scoring, a
real vision pipeline, real voice I/O, new agents, and a creative-content
layer are the natural next phase of work, not yet scheduled — see
`docs/architecture_baseline.md` §11–12 for the current known-limitations
list.
