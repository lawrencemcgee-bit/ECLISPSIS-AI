"""
BackupService: automatic rotating backups for settings, profile, and session state.
Milestone 7 Step 11: auto-backup + corruption recovery.
"""

import json
import os
import shutil
import time

class BackupService:
    def __init__(self):
        self.base_dir = os.path.join(os.getcwd(), "data")
        self.backup_dir = os.path.join(self.base_dir, "backup")
        self.max_backups = 5
        self._ensure_dirs()

    def _ensure_dirs(self):
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)

    def _timestamp(self):
        return time.strftime("%Y%m%d-%H%M%S")

    def backup_file(self, filename):
        src = os.path.join(self.base_dir, filename)
        if not os.path.exists(src):
            return

        ts = self._timestamp()
        dst = os.path.join(self.backup_dir, f"{filename}.{ts}.bak")

        shutil.copy(src, dst)
        self._rotate(filename)

    def _rotate(self, filename):
        files = sorted(
            [f for f in os.listdir(self.backup_dir) if f.startswith(filename)],
            reverse=True
        )
        while len(files) > self.max_backups:
            old = files.pop()
            os.remove(os.path.join(self.backup_dir, old))

    def restore_latest(self, filename):
        files = sorted(
            [f for f in os.listdir(self.backup_dir) if f.startswith(filename)],
            reverse=True
        )
        if not files:
            return None

        latest = os.path.join(self.backup_dir, files[0])
        dst = os.path.join(self.base_dir, filename)
        shutil.copy(latest, dst)
        return latest
