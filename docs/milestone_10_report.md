# Milestone 10 Report — Security & Permissions

## 1. Summary
Milestone 10 replaced the auto-approve `PermissionService` with a real,
fail-closed permission system (persisted grants/denials, an optional
interactive decision handler), turned `SafetyRules` into a genuinely
configurable policy engine, and — this is the part that actually matters —
wired enforcement into the two real sensitive actions that existed
(`capture_vision`, `toggle_mic`), which previously ran unconditionally
regardless of what `SafetyRules` claimed the policy was.

## 2. Before

**`PermissionService.request()`** unconditionally returned `True`:
```python
def request(self, permission: str) -> bool:
    self.events.emit("permission.requested", {"permission": permission})
    # Milestone 4: auto-approve (UI will handle real approval later)
    return True
```
Every permission-gated action was already effectively unprotected.

**`SafetyRules`** held `access_camera_without_permission` and
`access_microphone_without_permission` in its *permanently blocked* set —
meaning, despite the names, these could never be allowed no matter what,
because nothing ever checked for a granted permission before returning
`False` for them. The policy was self-contradictory and, separately,
**nothing enforced it anyway**: `capture_vision()` and `toggle_mic()`
called their services directly with no call into `VerificationService` at
all. The policy existed on paper and was enforced nowhere.

## 3. After

**`SafetyRules`** now separates two real concepts:
- `blocked_actions` — permanently forbidden regardless of permission
  (`delete_system_files`, `run_shell_command`)
- `permission_required_actions` — allowed only with a granted permission
  (`access_camera`, `access_microphone`, clean names, decoupled from grant
  state)

Both sets are mutable at runtime (`block`/`unblock`,
`require_permission`/`allow_without_permission`) for future config-driven
policy.

**`PermissionService`** now persists decisions via `PersistenceService`
(new `data/permissions.json`, following the same JSON pattern as
settings/profile/session), supports `grant()`/`deny()`/`revoke()`, accepts
an optional `set_decision_handler(fn)` for a future interactive UI, and —
the actual fix — **fails closed**: no prior decision and no handler means
denied, not approved.

**`VerificationService`** now asks `SafetyRules.requires_permission()` as
the default when a caller doesn't explicitly pass
`requires_permission=True/False` — existing callers that do pass it
explicitly (`AssistantCore`'s `"conversation"` action) are unaffected.

**Enforcement is now real**, not just declared:
```python
def capture_vision(self):
    if not self.verification.verify("access_camera", {}):
        self.events.emit("vision.blocked", {"reason": "permission_denied"})
        return None
    ...

def toggle_mic(self):
    if not self.audio.active:
        if not self.verification.verify("access_microphone", {}):
            self.events.emit("audio.blocked", {"reason": "permission_denied"})
            return self.audio.active
        ...
```
Turning the mic **off** stays ungated — stopping capture is always safe.

`AssistantCore` gained `grant_permission()`, `deny_permission()`,
`revoke_permission()`, `list_permissions()`, and
`set_permission_decision_handler()`. `get_diagnostics()` (Phase 9) gained
a `"security"` subsystem entry: granted/denied counts, blocked-action
count, and whether an interactive handler is wired — so the diagnostics
snapshot now reports security posture alongside engine/voice/vision/audio.

## 4. Files Changed
- `src/core/safety_rules.py` — rewritten (hard-blocked vs
  permission-gated sets; camera/mic moved out of permanent block)
- `src/core/permission_service.py` — rewritten (fail-closed, persisted,
  decision handler)
- `src/core/verification_service.py` — SafetyRules supplies the default
  `requires_permission` signal
- `src/core/persistence_service.py` — added `load_permissions()` /
  `save_permissions()`
- `src/core/assistant_core.py` — `capture_vision()`/`toggle_mic()` now
  enforce; new grant/deny/revoke/list/decision-handler methods; security
  entry in `get_diagnostics()`
- `test_all_phases.py` — new `Phase10Security` (8 tests); three existing
  Phase 6 tests updated (see §5 — this needed a deliberate, documented
  behavior change, not a silent one)

## 5. Behavior Change (deliberate, not incidental)
`test_toggle_mic_and_events`, `test_mic_state_restored_on_restart`, and
`test_vision_and_voice_events_fire` previously exercised
`toggle_mic()`/`capture_vision()` with no permission step, because none
existed. They now call `assistant.grant_permission(...)` first. This is
the intended effect of this milestone — mic/camera access that was
silently unconditional is now consent-gated — so updating tests to grant
first is how the new, correct behavior gets covered, not a workaround.
The **previous, ungated behavior is separately tested as a regression**:
`Phase10Security.test_camera_access_fails_closed_by_default` and
`test_microphone_access_fails_closed_by_default` assert the fail-closed
default explicitly.

## 6. Checks Run & Results
Full suite: `python test_all_phases.py`
- 44 tests total (36 pre-existing + 8 new), all passing, 1 skip (PySide6
  not installed in this environment — pre-existing, unrelated)
- New tests cover: fail-closed defaults for camera and mic, grants
  surviving restart, deny + revoke, the interactive decision handler being
  consulted once then superseded by the persisted grant, hard-blocked
  actions ignoring any permission grant, `SafetyRules`' runtime mutability,
  and the new `security` diagnostics entry

## 7. Behavior Preserved
`start_voice_listening()`/`stop_voice_listening()` (Phase 7's `VoiceService`
listening flag) are **not** gated by this milestone — see Known
Limitations. The `"conversation"` action's always-allowed path is
unchanged (`requires_permission: False` passed explicitly, short-circuits
before any permission check, exactly as before).

## 8. Known Limitations
- `start_voice_listening()` is conceptually related to microphone access
  but is a separate stub subsystem (`VoiceService`'s listening flag, not
  `AudioService`). Deciding whether it should share the `access_microphone`
  permission or need its own is a real design question, not obvious enough
  to decide unilaterally in this milestone — flagging for a deliberate
  choice rather than guessing.
- No UI exists yet to call `set_permission_decision_handler()` with
  something real — until then, every ungranted request fails closed,
  which is correct but means vision/mic are unusable end-to-end without
  either pre-granting via `grant_permission()` or a future approval
  dialog.
- **Separately, unrelated to this milestone's scope**: while auditing
  call sites for this work, `src/ui/plugin_panel.qml` was found to
  contain a stale, drifted duplicate of an early `assistant_core.py`
  (Python code with a `.qml` extension — missing Phases 6/8/9/10 entirely,
  different method names). It's inert at runtime (invalid QML, never
  loaded), but it's confusing dead weight sitting in `src/ui/`. Flagging
  rather than deleting it silently — let me know if you'd like it removed
  as a quick cleanup pass.
- `config/config_manager.py` and `config/settings.yaml` are also unused
  anywhere in `src/` (same class of issue Phase 9 found and fixed for
  `observability.py`). Not touched here to stay scoped to Security &
  Permissions — worth its own small pass.

## 9. Next Milestone
Proceed to Milestone 11 — Cross-Platform API: stand up the FastAPI app
already declared in `pyproject.toml`, exposing `/message`, `/nci/score`,
`/vision/analyze`, `/diagnostics`, etc. `get_diagnostics()` and the
permission/verification layer are now real enough to be worth exposing
over HTTP.
