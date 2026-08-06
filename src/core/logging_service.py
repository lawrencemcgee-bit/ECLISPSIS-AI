"""
LoggingService: structured JSON logging to logs/app.log
Milestone 7: event, agent, conversation, error logs.
"""

import json
import os
import datetime
import traceback

class LoggingService:
    def __init__(self):
        self.base_dir = os.path.join(os.getcwd(), "logs")
        self.log_path = os.path.join(self.base_dir, "app.log")
        self._ensure_dirs()

    def _ensure_dirs(self):
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)

    def _timestamp(self):
        # Python 3.12+ deprecated datetime.utcnow() in favor of a
        # timezone-aware call; utcnow() is slated for removal in a future
        # Python version. isoformat() on an aware UTC datetime includes
        # "+00:00" instead of a bare "Z", so it's stripped and appended
        # explicitly to keep the exact same log format as before.
        return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "") + "Z"

    def log(self, level: str, event: str, payload: dict | None = None):
        entry = {
            "ts": self._timestamp(),
            "level": level,
            "event": event,
            "payload": payload or {}
        }
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def info(self, event: str, payload: dict | None = None):
        self.log("INFO", event, payload)

    def warn(self, event: str, payload: dict | None = None):
        self.log("WARN", event, payload)

    def error(self, event: str, payload: dict | None = None):
        self.log("ERROR", event, payload)

    def exception(self, event: str, exc: Exception):
        self.log("ERROR", event, {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc()
        })
