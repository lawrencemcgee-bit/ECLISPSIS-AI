"""
SafetyRules defines the assistant's action policy: a small set of actions
that are permanently blocked regardless of permission, and a separate set
of actions that are allowed only once a specific permission has been
granted.

Phase 10 fix: "access_camera_without_permission" and
"access_microphone_without_permission" previously sat in the *permanently*
blocked set — meaning camera/microphone access could never be allowed, no
matter what, despite the names implying they'd become fine "with
permission". No code path ever actually checked for a granted permission
before returning false for them; the policy was defined but never
enforceable. That's fixed here by moving camera/microphone access into the
permission-gated set below, under plain action names decoupled from
whether permission was granted.

Both sets are mutable at runtime (block/unblock, require_permission/
allow_without_permission) so a future config-driven policy loaded from
settings can adjust them without editing this file.
"""

class SafetyRules:
    def __init__(self):
        # Permanently forbidden, regardless of any granted permission.
        self.blocked_actions = {
            "delete_system_files",
            "run_shell_command",
        }

        # Allowed only once PermissionService has a granted decision for
        # the same action name (see PermissionService.request()).
        self.permission_required_actions = {
            "access_camera",
            "access_microphone",
        }

    def is_allowed(self, action: str) -> bool:
        """Hard policy only — does not consider permission grants. An
        action can fail here (permanently blocked) or pass here but still
        need a permission (see requires_permission)."""
        return action not in self.blocked_actions

    def requires_permission(self, action: str) -> bool:
        return action in self.permission_required_actions

    def block(self, action: str):
        """Permanently forbid an action. Removes it from the
        permission-gated set if present — a hard block always wins."""
        self.permission_required_actions.discard(action)
        self.blocked_actions.add(action)

    def unblock(self, action: str):
        self.blocked_actions.discard(action)

    def require_permission(self, action: str):
        """Marks an action as needing a granted permission. No-op if the
        action is already hard-blocked — unblock() it first if that's
        really the intent."""
        if action not in self.blocked_actions:
            self.permission_required_actions.add(action)

    def allow_without_permission(self, action: str):
        self.permission_required_actions.discard(action)
