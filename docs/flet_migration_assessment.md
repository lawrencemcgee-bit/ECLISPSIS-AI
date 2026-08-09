# Flet UI Migration Assessment

Written as a working design document, not a finished decision record —
this is a proposal and a first build pass, not a completed migration.
`src/ui/` (PySide6/QML) has not been touched or removed. `flet_run.py` is
a new, additive third frontend alongside `run.py` and `api.py`.

## 0. On the stated reason for migrating

For the record, since it affects how this should be sequenced: the
diagnostic evidence gathered earlier in this project did not confirm a
genuine PySide6/Python 3.13 incompatibility. PySide6 6.10.2 (what's
pinned) officially supports 3.13. The specific error hit
(`DLL load failed while importing QtGui: The specified procedure could
not be found`) was reproduced elsewhere on Python 3.12 as well as 3.13,
which points to a Windows environment/DLL issue rather than a Python
version wall. That's noted here once, plainly, and then set aside — this
is a legitimate technical direction regardless of the original trigger,
and the rest of this document treats it as a real decision to build
toward, not something to keep re-litigating.

**Ironic wrinkle worth knowing before committing further**: Flet itself
is currently mid a large, breaking rewrite toward a 1.0 release (as of
Aug 2026, the latest stable is 0.86.1; blog posts reference a "1.0 RC" at
0.90; `UserControl`, the older custom-component pattern, is already
deprecated). Migrating away from PySide6 partly to escape one framework's
instability, onto a framework that is itself mid-rewrite, carries its own
version-churn risk. Worth going in with eyes open, not as a reason not to
proceed.

## 1. What's confirmed vs. designed vs. guessed

| Claim | Confidence | Why |
|---|---|---|
| `AssistantCore` and every service under `src/core`, `src/agents`, `src/services`, `src/plugins`, `src/engine` are 100% UI-framework-agnostic | **Confirmed** | Grepped for PySide6/Qt imports across all of them — zero matches. This is the fact the whole migration plan depends on, and it checks out. |
| Flet can plug into `AssistantCore` the same way the FastAPI layer does (Milestone 11) | **High** | Same pattern, proven twice already (QML's `StateBridge`, the API's `create_app(assistant)`). `FletBridge` is the third implementation of that same pattern. |
| The exact Flet API calls used in this code (`page.window.width`, `page.open(SnackBar(...))`, `animate_scale`, `page.run_task`) | **Medium** | Reviewed against Flet ~0.86 docs and release notes, never executed — no network access to install Flet in the environment this was written in. Flagged individually in code comments where version churn is most likely (window API, animation properties, SnackBar). |
| The "holographic" visual fidelity for Nova | **Low-Medium** | Flet has no shader/GLSL access. What's built is layered glow via `BoxShadow` + low-opacity blur — a reasonable approximation, not true holography. |
| Voice I/O (real STT/TTS, "available free personas and voices") | **Not built** | See §5. This was scoped as a UI migration; voice input/output doesn't exist anywhere in this codebase yet (`VoiceService` is still a state-machine-only placeholder, unchanged since Milestone 6). |

## 2. Architecture

```
src/ui_flet/
  bridge.py                 — FletBridge: persona-agnostic, mirrors
                               StateBridge's responsibilities
  personas/
    nova/
      theme.py               — color tokens, glass_panel()
      orb.py                 — reactive central orb (Stack + attached methods)
      waveform.py             — bar visualizer driven by AudioService samples
      app.py                  — full screen, wires bridge + components
    lyra/
      theme.py                — distinct warm palette
      app.py                  — command-console screen (lighter build — see §4)
flet_run.py                  — entry point: `python flet_run.py --persona nova|lyra [--web]`
```

**Why composition instead of subclassing `ft.Control`/`UserControl`**:
`UserControl` is deprecated in the run-up to Flet 1.0, and subclassing
`ft.Control` directly is a newer, less battle-tested pattern that could
still shift before 1.0 ships. `orb.py` and `waveform.py` instead build
plain `ft.Stack`/`ft.Row` trees and attach a couple of extra methods
(`set_state`, `set_samples`) directly onto the returned control object.
Flet controls are ordinary Python objects — this works today and doesn't
depend on whichever custom-component API Flet settles on for 1.0.

**One genuine advantage over the QML approach, confirmed not assumed**:
Milestone 13's verification pass flagged an unresolved risk —
`main_window.qml` reads nested attributes (`assistant.profile.preferences...`)
off a plain, non-`QObject` Python instance exposed via
`setContextProperty()`, and whether QML's meta-object system reliably
supports that is genuinely version-dependent and was never confirmed
either way. That risk doesn't exist in the Flet build: there's no
separate QML/JS engine doing attribute marshalling. `FletBridge` reads
`assistant.profile`, `assistant.settings`, etc. as plain Python attribute
access, because that's all it ever is.

## 3. Approach 1 — Nova (Jarvis-style)

**Intent**: an ambient, reactive command center. A central orb is the
focal point — it changes color and pulse rhythm with `AssistantCore`'s
state (idle / listening / thinking / speaking / error, via the existing
`state.changed` event, no new event needed). An agent "tool tray" sits
below it for direct one-tap agent invocation. Chat lives in a docked
glass panel rather than dominating the screen.

**Color language**: near-black background (`#05070D`), electric-cyan
accent (`#00D9FF`), glass panels via low-opacity + blur `Container`s.

**Built this pass**: full working screen — orb with continuous ambient
pulse (a background `asyncio` loop via `page.run_task`, distinct from
`AssistantCore.start_automation_ticker()`'s thread, since this needs a
much tighter refresh interval than the 30s automation cadence), waveform
tied to real `AudioService.get_samples()` output, agent tray, chat panel,
input bar with mic toggle.

**Deliberately not built this pass**: tool-trigger *visual* feedback
(e.g., the tray icon flashing when an agent completes — currently it just
runs silently and the result appears in chat), a settings/profile panel,
window-geometry restore beyond a first-launch size (`page.window.on_event`
wiring is present but untested).

## 4. Approach 2 — Lyra (voice-first command console)

**Intent**: minimal chrome, monospace transcript styled like a terminal,
a single command bar that's both a text input and a mic trigger. A
static persona avatar rather than Nova's animated orb. Slash-command
convention (`/weather`) for direct agent calls, versus Nova's tap-driven
tray — two different interaction philosophies over the same backend.

**Color language**: warm neutral background (`#12100E`), amber accent
(`#E8A96B`) — deliberately far from Nova's palette so the two read as
different products, not a reskin.

**Scope cut, stated plainly**: this pass built a lighter skeleton than
Nova — static avatar (no pulse loop), no waveform wired in, chat bubbles
reuse `FletBridge`'s default builder rather than a console-specific one.
Bringing it to full parity is mechanical (the same patterns `orb.py`/
`waveform.py` already demonstrate), just not done in this pass given the
size of building two complete UIs in one sitting.

## 5. What this migration does NOT include

- **Real voice I/O.** "Free personas and voices" implies actual
  speech-to-text and text-to-speech. Neither exists anywhere in this
  codebase — `VoiceService` (`src/services/voice_service.py`) is a
  listening-state machine only, unchanged since Milestone 6. Free/open
  options worth evaluating when that gets built: `pyttsx3` (offline TTS,
  uses OS-installed voices, genuinely free, no API key), `Vosk` (offline
  STT models, free/open), or the browser's Web Speech API if `flet_run.py
  --web` is the target (free, but browser-dependent, not available on a
  native desktop window). None of these have been evaluated hands-on here
  — this is a pointer for the next piece of work, not a recommendation
  made from testing.
- **Deprecating/removing `src/ui/` (QML).** Left fully intact. That's a
  separate decision from building this.
- **Packaging** (`flet build` for a distributable exe/app). Not attempted.

## 6. Status update — Nova selected

**Decision**: Nova is the persona being committed to. Lyra remains in the
repo as-is (not deleted, not deprioritized in code — just not the active
target for further work) unless a later decision says otherwise.

**Confirmed working via actual hands-on testing** (not just review — this
is the first part of the whole Flet migration that's moved from "reviewed
but never run" to "verified against a real launch"):
- Window launches, orb renders and pulses correctly
- Chat send/receive round-trips through `AssistantCore.process_message()`
- Agent tool tray (Notes/Weather/News) executes end-to-end
- Mic and camera both correctly fail closed with a toast (Phase 10's
  permission system working through this new UI, not a bug)
- Window layout no longer clips the input bar

**Real bugs found and fixed along the way** (documented here since they
were genuine mistakes, not just version guesses that happened to be
wrong): `ft.alignment.center` → `ft.Alignment.CENTER`; confirmed
`ft.border.all` (lowercase) is in fact correct, reversing an incorrect
"fix" attempt; `ft.app()` → `ft.run()` (deprecated); `page.open()` doesn't
exist on this Page — `page.show_dialog()` is correct; and a real Flet
layout bug — `expand=True` on a child does nothing without a parent that
actually stretches to give it bounded width, which was hiding the entire
input bar.

## 7. Suggested sequencing

Given the size of what "full parity, both personas, voice-enabled" would
actually mean, treating this as staged work rather than one big-bang
cutover:

1. ~~Install and smoke-test what's here~~ — **done**. Several real bugs
   found and fixed via actual hands-on runs (§6).
2. ~~Bring Lyra to parity with Nova, OR pick one persona to commit to~~ —
   **decided: Nova.** Lyra stays in the repo, unmaintained going forward
   unless that changes.
3. Add remaining Nova coverage: window geometry restore (`page.window.on_event`
   is wired but not yet confirmed working — resize was tested, restore
   across a restart wasn't), a settings/profile panel, tool-tray visual
   feedback on agent completion.
4. Evaluate the free voice options in §5 as their own scoped piece of
   work — this is genuinely separate from the UI framework choice and is
   the last major gap between what's built and "voice-first" as originally
   requested.
5. Only after 3–4: decide whether `src/ui/` (QML) gets deprecated, kept
   as a fallback, or removed.

## 8. Tutorial — Flet concepts used in this build

Written for genuine knowledge transfer, not just documentation of what
was done.

**The core mental model shift from QML**: QML is *declarative* — you
write `text: assistant.session_state.draft` and the QML engine
re-evaluates that binding automatically whenever a dependency changes.
Flet is *imperative* — nothing updates on its own. You directly mutate a
Python object's property (`some_container.bgcolor = "#FF0000"`) and then
explicitly call `.update()` on it (or `page.update()` for everything).
Miss the `.update()` call and the change happens in memory but never
reaches the screen. This is the single most common Flet bug for people
coming from declarative UI frameworks.

**`Page`**: the root object representing one running app window (or one
browser tab, in web mode). Everything you add to the screen ultimately
traces back to `page.controls` or something added via `page.add(...)`.
`ft.app(target=main)` calls your `main(page)` function once per session
and hands you this object.

**Controls**: every visible thing (`ft.Container`, `ft.Text`,
`ft.Row`, `ft.Column`, `ft.TextField`, `ft.IconButton`...) is a Python
object with properties you set directly. Composing them by nesting
(`ft.Row(controls=[...])`) is how layout works — there's no separate
layout language.

**Event handlers**: `on_click=my_function` (or a `lambda e: ...`) — `e`
is an event object; you usually don't need it for simple cases. This
replaces QML's `Signal`/`Slot`/`onClicked:` entirely.

**`page.run_task(coroutine_function)`**: schedules an `async def`
function on the page's own asyncio event loop. This is how Nova's orb
achieves a continuous pulse (`orb.py`'s `_pulse_loop`) — a `while True:`
loop with `await asyncio.sleep(...)` between frames, cancelled via
`task.cancel()` when no longer needed (see `stop_pulse()`). This is
distinct from `AssistantCore.start_automation_ticker()`, which is a plain
`threading.Thread` — that one exists because `AssistantCore` is shared
across frontends that may or may not have an asyncio loop running (the
QML/PySide6 frontend doesn't); a Flet-hosted process could technically
use `page.run_task` for that too, but the thread-based ticker already
works identically regardless of which frontend is hosting it, so
`flet_run.py` reuses it rather than building a second mechanism.

**Why `attach()` exists as a separate step from `FletBridge.__init__`**:
the bridge needs to exist before a persona can build controls that
reference it (button `on_click` handlers close over `bridge`), but it
can't push chat history into a `ListView` that doesn't exist yet. Splitting
construction from attachment resolves that ordering — construct the
bridge, build the persona's controls (which can already call bridge
methods from event handlers), then call `bridge.attach(chat_list=...)`
once those controls exist.

## 9. How to actually run this

```bash
pip install flet==0.86.1
python flet_run.py                  # Nova, native window
python flet_run.py --persona lyra   # Lyra, native window
python flet_run.py --web            # Nova, opens in a browser tab instead
```

None of the three have been run in this environment (no Flet install
possible here — see the confidence table in §1). The first real run on
your machine is genuinely the first time any of this code executes.
Please report back whatever breaks; given the Medium-confidence items
flagged throughout, something breaking on the first try should be
expected, not alarming.
