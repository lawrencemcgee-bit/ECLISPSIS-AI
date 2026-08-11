# src/ui/ (QML/PySide6) — Deprecated

As of the Tier 2 repo-hygiene pass, this UI is **deprecated**: kept in the
repository as a documented fallback, receiving no further work.

**Why**: `src/ui_flet/` (Nova persona) is now the actively developed,
hands-on-tested UI — window geometry restore, voice settings panel,
tool-tray feedback, a speaking-state orb reaction, and a full real
voice I/O loop (Vosk STT + pyttsx3 TTS) are all confirmed working there.
This QML build predates that work and has an unresolved, never-confirmed
risk noted in `docs/architecture_baseline.md` §9: whether Qt's
meta-object system reliably marshals nested attribute access
(`assistant.profile.preferences...`) off a plain non-`QObject` Python
instance is version-dependent and was never verified either way.

**What this means in practice**:
- `run.py` → `run_qml_ui(assistant)` still works and is not being removed.
- No new features land here; bugs found in `src/ui_flet/` are not
  ported back.
- If PySide6/Qt6 becomes unavailable in a given environment, this is a
  known, accepted gap — use `flet_run.py` instead.

See `docs/architecture_baseline.md` and `docs/flet_migration_assessment.md`
§7 for the full history behind this decision.
