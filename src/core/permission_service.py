"""
PermissionService ensures user consent before performing sensitive actions.

Phase 10: Milestone 4's request() unconditionally returned True —
"auto-approve (UI will handle real approval later)" — meaning every
permission-gated action was already effectively unprotected. That gap is
closed here:

- Decisions are persisted (granted/denied) via PersistenceService, so a
  choice made once doesn't need to be re-asked every run.
- An optional decision handler can be registered (set_decision_handler) —
  meant for a real UI approval dialog in a later milestone — and is
  consulted for anything not already decided.
- With no prior decision and no decision handler registered, requests
  fail closed (denied) rather than auto-approving. There's no one to ask
  yet, so consent cannot be assumed.
"""

from src.core.event_bus import EventBus


class PermissionService:
    def __init__(self, events: EventBus, persistence=None):
        self.events = events
        self.persistence = persistence
        self.granted = set()
        self.denied = set()
        self._decision_handler = None
        if self.persistence is not None:
            self._load()

    def _load(self):
        data = self.persistence.load_permissions()
        self.granted = set(data.get("granted", []))
        self.denied = set(data.get("denied", []))

    def _save(self):
        if self.persistence is not None:
            self.persistence.save_permissions({
                "granted": sorted(self.granted),
                "denied": sorted(self.denied),
            })

    def set_decision_handler(self, handler):
        """Registers a callable(permission: str) -> bool used to resolve a
        request that has no prior decision. Intended to be wired to a real
        UI approval dialog in a future milestone. Pass None to unregister."""
        self._decision_handler = handler

    def grant(self, permission: str):
        self.denied.discard(permission)
        self.granted.add(permission)
        self._save()
        self.events.emit("permission.granted", {"permission": permission})

    def deny(self, permission: str):
        self.granted.discard(permission)
        self.denied.add(permission)
        self._save()
        self.events.emit("permission.denied", {"permission": permission})

    def revoke(self, permission: str):
        """Clears any prior decision (granted or denied) so the next
        request for it is resolved fresh."""
        self.granted.discard(permission)
        self.denied.discard(permission)
        self._save()
        self.events.emit("permission.revoked", {"permission": permission})

    def request(self, permission: str) -> bool:
        self.events.emit("permission.requested", {"permission": permission})

        if permission in self.granted:
            return True
        if permission in self.denied:
            return False

        if self._decision_handler is not None:
            decision = bool(self._decision_handler(permission))
            if decision:
                self.grant(permission)
            else:
                self.deny(permission)
            return decision

        # Fail closed: no persisted decision and no interactive handler
        # means real consent cannot be obtained right now, so it must not
        # be assumed. This is the Phase 10 fix — previously this path
        # returned True unconditionally.
        self.events.emit("permission.denied", {
            "permission": permission,
            "reason": "no_decision_handler",
        })
        return False
