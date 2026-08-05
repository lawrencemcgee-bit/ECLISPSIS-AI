"""
UserProfileService: persistent user profile storage.
Milestone 7: name, avatar, preferences.
"""

import json
import os

class UserProfileService:
    def __init__(self):
        self.base_dir = os.path.join(os.getcwd(), "data")
        self.profile_path = os.path.join(self.base_dir, "user_profile.json")
        self._ensure_dirs()

    def _ensure_dirs(self):
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)

    def load(self):
        if not os.path.exists(self.profile_path):
            return {
                "name": "User",
                "avatar": "default.png",
                "preferences": {
                    "show_typing_indicator": True,
                    "enable_sound_effects": False
                }
            }
        with open(self.profile_path, "r") as f:
            return json.load(f)

    def save(self, profile: dict):
        with open(self.profile_path, "w") as f:
            json.dump(profile, f, indent=4)
