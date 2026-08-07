"""
VerificationService ensures safety, validity, and correctness of actions.

Phase 10: when a caller doesn't explicitly say whether an action needs
permission (payload.get("requires_permission") is None), SafetyRules now
supplies that default instead of every caller having to know which
actions are permission-gated. Callers that already pass
requires_permission=True/False explicitly (e.g. AssistantCore's
"conversation" action) are unaffected — this only fills the gap when
they don't say.
"""

from src.core.safety_rules import SafetyRules

class VerificationService:
    def __init__(self, permissions):
        self.rules = SafetyRules()
        self.permissions = permissions

    def verify(self, action: str, payload: dict) -> bool:
        # Rule-based safety check — a hard block always wins, regardless
        # of any permission.
        if not self.rules.is_allowed(action):
            return False

        requires_permission = payload.get("requires_permission")
        if requires_permission is None:
            requires_permission = self.rules.requires_permission(action)

        if requires_permission:
            return self.permissions.request(action)

        return True
