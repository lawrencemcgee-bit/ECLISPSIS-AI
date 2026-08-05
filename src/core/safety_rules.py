"""
SafetyRules defines the allowed and disallowed actions for the assistant.
Milestone 4: simple rule-based system.
"""

class SafetyRules:
    def __init__(self):
        self.blocked_actions = {
            "delete_system_files",
            "access_camera_without_permission",
            "access_microphone_without_permission",
            "run_shell_command",
        }

    def is_allowed(self, action: str) -> bool:
        return action not in self.blocked_actions
