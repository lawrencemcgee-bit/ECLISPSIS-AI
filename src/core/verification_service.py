"""
VerificationService ensures safety, validity, and correctness of actions.
Milestone 4: integrates SafetyRules + PermissionService.
"""

from src.core.safety_rules import SafetyRules

class VerificationService:
    def __init__(self, permissions):
        self.rules = SafetyRules()
        self.permissions = permissions

    def verify(self, action: str, payload: dict) -> bool:
        # Rule-based safety check
        if not self.rules.is_allowed(action):
            return False

        # Permission check
        if payload.get("requires_permission"):
            return self.permissions.request(action)

        return True

