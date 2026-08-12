"""
ApiKeyService — API-key authentication for the HTTP API layer only.

AssistantCore itself has no concept of "API keys" — the desktop QML/Flet
UIs call it in-process and never go over HTTP, so they don't need one.
This exists purely for src/api/api_app.py, gating remote access the same
way PermissionService already gates camera/mic access for local
capabilities — Milestone 11's known limitation ("anything that can reach
the port can call every route", see docs/milestone_11_report.md) is what
this fixes.

Security notes:
  - Keys are generated with `secrets.token_urlsafe` (cryptographically
    random, URL-safe). Only a SHA-256 hash of each key is ever persisted
    to disk — the raw value exists in memory for exactly as long as the
    call that created it, then is handed back to the caller once and
    never stored or logged again. A lost key can't be recovered, only
    revoked and replaced with a new one — same tradeoff as a password
    hash, deliberately.
  - Verification is a hash-and-compare, not a stored-plaintext comparison
    — a leaked api_keys.json doesn't hand over usable keys, only hashes.
  - Storage is a small local JSON file (data/api_keys.json), same
    directory/pattern PersistenceService already uses for everything
    else, but kept as its own file/service rather than folded into
    PersistenceService: this is an HTTP-layer concern, not something
    AssistantCore's non-HTTP consumers (QML, Flet) have any reason to
    know about.
"""

import hashlib
import json
import os
import secrets


class ApiKeyService:
    """Recovery note: if every key is ever revoked, `has_any_key()` goes
    back to False, so the next server start regenerates a fresh bootstrap
    key the same way first-run does — a full lockout self-heals on
    restart rather than requiring manual file surgery on api_keys.json."""

    def __init__(self, base_dir: str = None):
        self.base_dir = base_dir or os.path.join(os.getcwd(), "data")
        self.path = os.path.join(self.base_dir, "api_keys.json")
        os.makedirs(self.base_dir, exist_ok=True)
        self._keys = self._load()

    def _load(self) -> dict:
        if not os.path.exists(self.path):
            return {}
        with open(self.path, "r") as f:
            return json.load(f)

    def _save(self):
        with open(self.path, "w") as f:
            json.dump(self._keys, f, indent=4)

    @staticmethod
    def _hash(raw_key: str) -> str:
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def generate_key(self, label: str = "default") -> str:
        """Returns the RAW key. This is the only moment it's ever
        available — persist only stores its hash (see module docstring)."""
        raw = secrets.token_urlsafe(32)
        self._keys[self._hash(raw)] = {"label": label}
        self._save()
        return raw

    def revoke_key(self, raw_key: str) -> bool:
        digest = self._hash(raw_key)
        if digest in self._keys:
            del self._keys[digest]
            self._save()
            return True
        return False

    def verify(self, raw_key: str) -> bool:
        if not raw_key:
            return False
        return self._hash(raw_key) in self._keys

    def list_keys(self) -> list:
        """Redacted — labels only. Neither the raw key nor its hash is
        ever returned once generate_key() has handed the raw value back."""
        return [{"label": v["label"]} for v in self._keys.values()]

    def has_any_key(self) -> bool:
        return bool(self._keys)
