# Milestone 11 Report — Cross-Platform API

## 1. Summary
Milestone 11 stood up the FastAPI layer that `pyproject.toml` and the
Makefile's `start-api` target had both been pointing at since before this
milestone, with nothing behind either of them. It exposes `AssistantCore`
over HTTP — one shared instance, same principle Phase 2 used for the
desktop bootstrap — covering every capability that actually exists
(message processing, NCI scoring, vision capture, plugins, diagnostics,
permissions) and returning explicit `501`s for endpoints the original
design prompt named but that have no real backing logic yet.

## 2. Before
- `pyproject.toml` declared `fastapi==0.141.1`, `uvicorn==0.52.1`,
  `httpx>=0.27.0` as dependencies. Nothing in `src/` imported any of them.
- `Makefile` had a `start-api: uvicorn api:app --reload` target pointing
  at a top-level `api.py` module with a module-level `app` object that
  didn't exist — running `make start-api` would fail immediately.
- No HTTP surface existed at all; the QML desktop UI was the only client.

## 3. After

**`src/api/api_app.py`** — `create_app(assistant)` factory (mirrors
`run_qml_ui(assistant)`: takes the one shared instance rather than
constructing its own):

| Method | Path | Backed by |
|---|---|---|
| POST | `/message` | `assistant.process_message()` |
| POST | `/nci/score` | `assistant.analyze()` |
| POST | `/vision/analyze` | `assistant.capture_vision()` — `403` if permission denied |
| GET | `/plugins` | `assistant.list_plugins()` |
| POST | `/plugins/{id}` | `assistant.execute_plugins()` |
| GET | `/diagnostics` | `assistant.get_diagnostics()` (Phase 9) |
| GET | `/permissions` | `assistant.list_permissions()` (Phase 10) |
| POST | `/permissions/grant`\|`deny`\|`revoke` | same |
| POST | `/nci/batch` | **501** — no batch-scoring mode in `NCIService` yet |
| GET | `/nci/latest` | **501** — NCI reports aren't persisted yet |
| GET | `/vision/latest` | **501** — vision results aren't persisted yet |
| POST | `/social/analyze` | **501** — no social-media agent exists yet |

The `501` responses return a JSON body (`{"feature": ..., "reason": ...}`)
rather than a bare error or, worse, fabricated data — a client hitting
them gets an honest, typed answer about what's actually missing.

Permission endpoints weren't in the original endpoint list, but without
them a remote client would hit Phase 10's fail-closed default on
`/vision/analyze` with no way to ever resolve it — added as a necessary
consequence of Phase 10, not scope creep for its own sake.

**`api.py`** (repo root) — constructs the shared `AssistantCore` the same
way `run.py` does, then calls `create_app()`. This is specifically what
makes the pre-existing `make start-api` target work for the first time.

## 4. Files Changed
- `src/api/__init__.py`, `src/api/api_app.py` — new
- `api.py` — new (repo root, matches the Makefile's existing target)
- `requirements.txt` — added `fastapi`, `uvicorn` (already in
  `pyproject.toml`; `requirements.txt` had drifted out of sync — same
  class of issue Phase 9 fixed for `psutil`)
- `test_all_phases.py` — new `Phase11CrossPlatformAPI` (6 tests, skipped
  as a whole class if `fastapi`/`httpx` aren't installed, same pattern the
  suite already used for PySide6)

## 5. Checks Run & Results — read this before trusting it
`python test_all_phases.py`: **50 tests, 44 passed, 7 skipped** (1
pre-existing PySide6 skip + all 6 new Phase 11 tests).

**I could not actually execute the 6 new API tests.** This sandbox has no
`fastapi`/`httpx`/`starlette` installed and no network access to install
them, so they skip rather than run — I have not proven this code works,
only written and carefully reviewed it against standard FastAPI/Pydantic
idioms. Please run `pip install -r requirements.txt` (or `uv sync`) and
`python test_all_phases.py` yourself; if anything fails, send me the
output and I'll fix it before we call this milestone done.

## 6. Behavior Preserved
No existing method on `AssistantCore` changed signature or behavior — this
milestone only adds a new way to reach the same methods. `run.py`/
`qml_app.py` are untouched; the desktop UI's code path is unaffected.

## 7. Known Limitations
- No auth/API-key layer — anything that can reach the port can call every
  endpoint, including granting itself camera/mic permission. Fine for
  local development; not fine to expose beyond localhost as-is. Worth a
  dedicated pass once there's an actual second client (mobile, etc.)
  consuming this.
- No request-rate limiting or input-size limits.
- The `501` endpoints (`nci/batch`, `nci/latest`, `vision/latest`,
  `social/analyze`) will need real implementations once their underlying
  services (real NCI scoring, result persistence, a social-media agent)
  exist — that work was scoped out of Milestones 9/10/11 and is still
  outstanding from the original re-engineering prompt.

## 8. Next Milestone
Per the roadmap: Milestone 12 — Automation & Proactive Assistance (a
scheduler/trigger system; nothing like this exists anywhere yet). Milestone
13 is Final Validation. Separately, the original prompt's domain-engine
work (real NCI scoring, real vision pipeline, real STT/TTS, coding/browser/
social agents, the creative layer) remains unstarted and isn't on the
original 14-phase roadmap at all — worth deciding where it fits once 12–13
are done.
