"""
Cross-platform HTTP API (Phase 11) — exposes AssistantCore over FastAPI so
a future mobile client, browser client, or any other frontend can talk to
the SAME assistant instance as the desktop QML UI, instead of each
frontend needing its own separate core. This is the same "one shared
instance" principle Phase 2 fixed for the desktop bootstrap
(run.py / qml_app.py) — see create_app()'s docstring.

Endpoints implemented here cover only capabilities that actually exist
elsewhere in the codebase (process_message, analyze, capture_vision,
plugins, diagnostics, permissions). /nci/score, /nci/batch, /nci/latest,
/vision/analyze, /vision/latest, /social/analyze, /coding/analyze,
/coding/diff, /creative/*, and /browser/fetch are backed by real local
logic (src/services/nci_service.py, social_content_service.py,
coding_service.py, creative_content_service.py, browser_service.py,
plus persisted history in AssistantCore/PersistenceService for the
batch/latest endpoints) as of Tier 3 — none of them call an external
API or execute the content/code they're given (see each service's
module docstring). /creative/* in particular is template/heuristic-
based, not an LLM — see creative_content_service.py's module docstring
for what that means for the honesty of its output. /browser/fetch
fetches exactly the one URL given and never follows a link on its own
— see browser_service.py's module docstring for the full scope. No
endpoint here is a 501 stub anymore; the pattern is kept below
(_not_implemented) for any future endpoint that genuinely has no
backing implementation yet, so a client gets a clear, typed answer
instead of either a faked result or a generic 404.

Permission endpoints (/permissions, /permissions/grant|deny|revoke)
weren't in the original endpoint list, but a remote client has no other
way to satisfy Phase 10's fail-closed default for camera/mic access —
without them, /vision/analyze would 403 forever with no way to resolve it
from outside the process.

Automation management endpoints (/automation/triggers and friends,
added in Tier 3) close the last pre-existing gap: AutomationService
(Phase 12) and AssistantCore's register_event_automation /
register_schedule_automation / unregister_automation /
set_automation_enabled / list_automations / automation_tick were only
ever callable from in-process Python — a remote client had no way to
define, inspect, pause, or remove a trigger. These routes are a thin
passthrough to those existing methods; no new automation logic lives
here. Two things a Python caller can do that an HTTP caller cannot,
by design, not oversight: (1) an event trigger's `predicate` is an
arbitrary Python callable and isn't JSON-serializable, so the HTTP
registration route has no predicate field at all — a caller who needs
payload filtering registers the trigger un-filtered and filters
downstream, or uses the in-process API directly; (2) action dicts are
passed through unvalidated at registration time, same as the
in-process API — malformed actions still only surface as a failure
when the trigger actually fires (see AssistantCore._execute_automation_
action), not at registration, so registering a trigger always succeeds
if the request shape itself is valid.

Tier 3: every route requires an API key (see src/api/api_key_service.py)
via a global FastAPI dependency, fixing Milestone 11's known limitation
that anything reaching the port could call every route. On first run
(no keys exist yet), one bootstrap key is generated and printed to
stdout — the only channel available to hand it to the operator, since
there's no other client already authenticated to receive it over the
API itself. /auth/keys lets an already-authenticated caller create
additional keys (e.g. one per client) and revoke ones no longer needed.
"""

import dataclasses
import sys

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from src.api.api_key_service import ApiKeyService
from src.core.assistant_core import AssistantCore


class MessageRequest(BaseModel):
    message: str


class NCIScoreRequest(BaseModel):
    text: str | None = None
    url: str | None = None
    topic: str | None = None


class NCIBatchItem(BaseModel):
    text: str | None = None
    url: str | None = None
    topic: str | None = None


class NCIBatchRequest(BaseModel):
    items: list[NCIBatchItem]


class SocialAnalyzeRequest(BaseModel):
    text: str
    platform: str = "generic"


class CodingAnalyzeRequest(BaseModel):
    code: str
    language: str = "python"


class CodingDiffRequest(BaseModel):
    old_code: str
    new_code: str
    old_label: str = "before"
    new_label: str = "after"


class CreativeHeadlinesRequest(BaseModel):
    topic: str
    count: int = 5
    seed: int | None = None


class CreativePromptRequest(BaseModel):
    genre: str | None = None
    seed: int | None = None


class CreativeOutlineRequest(BaseModel):
    topic: str
    content_type: str = "blog_post"


class CreativeCritiqueRequest(BaseModel):
    text: str


class BrowserFetchRequest(BaseModel):
    url: str


class PluginExecuteRequest(BaseModel):
    payload: dict = {}


class PermissionAction(BaseModel):
    permission: str


class RegisterEventTriggerRequest(BaseModel):
    event_name: str
    action: dict
    trigger_id: str | None = None
    persistent: bool = False
    # No `predicate` field: predicates are Python callables, not
    # JSON-serializable — see this module's docstring.


class RegisterScheduleTriggerRequest(BaseModel):
    interval_seconds: float
    action: dict
    trigger_id: str | None = None
    run_immediately: bool = False
    persistent: bool = True


class CreateKeyRequest(BaseModel):
    label: str = "default"


class RevokeKeyRequest(BaseModel):
    key: str


def _result_dict(result):
    """AssistantResult/AgentResult/TaskResult (src/core/results.py) are
    plain dataclasses — convert once, consistently, instead of every route
    hand-rolling its own response shape."""
    if dataclasses.is_dataclass(result):
        return dataclasses.asdict(result)
    return result


def _not_implemented(feature: str, reason: str):
    raise HTTPException(status_code=501, detail={"feature": feature, "reason": reason})


def create_app(assistant: AssistantCore, api_keys: ApiKeyService = None) -> FastAPI:
    """Factory, not a module-level app — mirrors run_qml_ui(assistant):
    the caller passes in the ONE shared AssistantCore instance rather than
    this module constructing its own. See /api.py at the repo root for the
    process entry point that does that construction (mirrors run.py).

    `api_keys` is injectable (defaults to a fresh ApiKeyService reading
    from data/api_keys.json) mainly so tests can pass in one they already
    hold a reference to, instead of having to re-derive it from app.state
    after the fact."""
    key_service = api_keys or ApiKeyService()

    bootstrap_key = None
    if not key_service.has_any_key():
        bootstrap_key = key_service.generate_key(label="bootstrap")
        # stdout, not the structured app log: this is a secret, and
        # logs/app.log is a persisted file that could end up copied,
        # committed, or shared — see ApiKeyService's module docstring.
        # Printing it once at boot is the same tradeoff Jupyter makes for
        # its own local-server tokens.
        print(
            "\n[ECLIPSIS-AI] No API key existed — generated one for this "
            f"server:\n\n    {bootstrap_key}\n\n"
            "Store this now. It will not be shown again; a lost key must "
            "be revoked (once you have another valid key) and replaced "
            "via POST /auth/keys.\n",
            file=sys.stderr,
        )
        assistant.logger.info("api_key.bootstrap_generated", {"label": "bootstrap"})

    async def require_api_key(x_api_key: str = Header(default=None)):
        if not key_service.verify(x_api_key):
            raise HTTPException(
                status_code=401,
                detail={"error": "invalid_or_missing_api_key",
                        "hint": "Send a valid key in the X-API-Key header."},
            )

    app = FastAPI(
        title="ECLIPSIS-AI API", version="0.1.0",
        dependencies=[Depends(require_api_key)],
    )
    app.state.assistant = assistant
    app.state.api_keys = key_service

    @app.post("/message")
    def post_message(body: MessageRequest):
        result = assistant.process_message(body.message)
        return _result_dict(result)

    @app.post("/nci/score")
    def post_nci_score(body: NCIScoreRequest):
        try:
            return assistant.analyze(body.text, url=body.url, topic=body.topic)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail={"error": str(exc)})

    @app.post("/nci/batch")
    def post_nci_batch(body: NCIBatchRequest):
        items = [item.model_dump() for item in body.items]
        try:
            return {"results": assistant.analyze_batch(items)}
        except ValueError as exc:
            raise HTTPException(status_code=422, detail={"error": str(exc)})

    @app.get("/nci/latest")
    def get_nci_latest(limit: int = 10):
        return {"reports": assistant.get_latest_nci_reports(limit)}

    @app.post("/vision/analyze")
    def post_vision_analyze():
        result = assistant.capture_vision()
        if result is None:
            raise HTTPException(
                status_code=403,
                detail={"error": "permission_denied", "permission": "access_camera"},
            )
        return {"result": result}

    @app.get("/vision/latest")
    def get_vision_latest(limit: int = 10):
        return {"captures": assistant.get_latest_vision_captures(limit)}

    @app.post("/social/analyze")
    def post_social_analyze(body: SocialAnalyzeRequest):
        result = assistant.agents.run("social", text=body.text, platform=body.platform)
        if result.metadata and result.metadata.get("error"):
            raise HTTPException(status_code=422, detail={"error": result.metadata["error"]})
        return {"result": result.output}

    @app.post("/coding/analyze")
    def post_coding_analyze(body: CodingAnalyzeRequest):
        result = assistant.agents.run("coding", action="analyze", code=body.code, language=body.language)
        if result.metadata and result.metadata.get("error"):
            raise HTTPException(status_code=422, detail={"error": result.metadata["error"]})
        return {"result": result.output}

    @app.post("/coding/diff")
    def post_coding_diff(body: CodingDiffRequest):
        result = assistant.agents.run(
            "coding", action="diff", old_code=body.old_code, new_code=body.new_code,
            old_label=body.old_label, new_label=body.new_label,
        )
        if result.metadata and result.metadata.get("error"):
            raise HTTPException(status_code=422, detail={"error": result.metadata["error"]})
        return {"result": result.output}

    @app.post("/creative/headlines")
    def post_creative_headlines(body: CreativeHeadlinesRequest):
        result = assistant.agents.run(
            "creative", action="headlines", topic=body.topic, count=body.count, seed=body.seed,
        )
        return {"result": result.output}

    @app.post("/creative/prompt")
    def post_creative_prompt(body: CreativePromptRequest):
        result = assistant.agents.run(
            "creative", action="writing_prompt", genre=body.genre, seed=body.seed,
        )
        return {"result": result.output}

    @app.post("/creative/outline")
    def post_creative_outline(body: CreativeOutlineRequest):
        result = assistant.agents.run(
            "creative", action="outline", topic=body.topic, content_type=body.content_type,
        )
        return {"result": result.output}

    @app.post("/creative/critique")
    def post_creative_critique(body: CreativeCritiqueRequest):
        result = assistant.agents.run("creative", action="critique", text=body.text)
        return {"result": result.output}

    @app.post("/browser/fetch")
    def post_browser_fetch(body: BrowserFetchRequest):
        result = assistant.agents.run("browser", url=body.url)
        if result.metadata and result.metadata.get("error"):
            raise HTTPException(status_code=422, detail={"error": result.metadata["error"]})
        return {"result": result.output}

    @app.post("/plugins/{plugin_id}")
    def post_plugin_execute(plugin_id: str, body: PluginExecuteRequest):
        return assistant.execute_plugins(plugin_id, body.payload)

    @app.get("/plugins")
    def get_plugins():
        return assistant.list_plugins()

    @app.get("/diagnostics")
    def get_diagnostics():
        return assistant.get_diagnostics()

    @app.get("/permissions")
    def get_permissions():
        return assistant.list_permissions()

    @app.post("/permissions/grant")
    def post_permission_grant(body: PermissionAction):
        assistant.grant_permission(body.permission)
        return assistant.list_permissions()

    @app.post("/permissions/deny")
    def post_permission_deny(body: PermissionAction):
        assistant.deny_permission(body.permission)
        return assistant.list_permissions()

    @app.post("/permissions/revoke")
    def post_permission_revoke(body: PermissionAction):
        assistant.revoke_permission(body.permission)
        return assistant.list_permissions()

    @app.get("/automation/triggers")
    def get_automation_triggers():
        return {"triggers": assistant.list_automations()}

    @app.post("/automation/triggers/event")
    def post_automation_trigger_event(body: RegisterEventTriggerRequest):
        trigger_id = assistant.register_event_automation(
            body.event_name, body.action,
            trigger_id=body.trigger_id, persistent=body.persistent,
        )
        return {"trigger_id": trigger_id}

    @app.post("/automation/triggers/schedule")
    def post_automation_trigger_schedule(body: RegisterScheduleTriggerRequest):
        trigger_id = assistant.register_schedule_automation(
            body.interval_seconds, body.action, trigger_id=body.trigger_id,
            run_immediately=body.run_immediately, persistent=body.persistent,
        )
        return {"trigger_id": trigger_id}

    @app.delete("/automation/triggers/{trigger_id}")
    def delete_automation_trigger(trigger_id: str):
        if trigger_id not in assistant.automation.triggers:
            raise HTTPException(status_code=404, detail={"error": "trigger_not_found"})
        assistant.unregister_automation(trigger_id)
        return {"unregistered": trigger_id}

    @app.post("/automation/triggers/{trigger_id}/enable")
    def post_automation_trigger_enable(trigger_id: str):
        if trigger_id not in assistant.automation.triggers:
            raise HTTPException(status_code=404, detail={"error": "trigger_not_found"})
        assistant.set_automation_enabled(trigger_id, True)
        return {"trigger_id": trigger_id, "enabled": True}

    @app.post("/automation/triggers/{trigger_id}/disable")
    def post_automation_trigger_disable(trigger_id: str):
        if trigger_id not in assistant.automation.triggers:
            raise HTTPException(status_code=404, detail={"error": "trigger_not_found"})
        assistant.set_automation_enabled(trigger_id, False)
        return {"trigger_id": trigger_id, "enabled": False}

    @app.post("/automation/tick")
    def post_automation_tick():
        """Manually fires any due schedule triggers, on demand, rather
        than waiting for start_automation_ticker()'s background interval —
        useful for a remote caller that wants to force a check right now,
        or for testing a schedule trigger without waiting."""
        return {"fired": assistant.automation_tick()}

    @app.get("/auth/keys")
    def get_auth_keys():
        """Redacted list only — see ApiKeyService.list_keys()."""
        return key_service.list_keys()

    @app.post("/auth/keys")
    def post_auth_keys(body: CreateKeyRequest):
        """Requires an already-valid key (the global dependency covers
        this route too) — there's no unauthenticated way to mint keys
        beyond the one-time bootstrap key printed at server startup."""
        raw = key_service.generate_key(body.label)
        return {
            "key": raw,
            "label": body.label,
            "warning": "Store this now — it will not be shown again.",
        }

    @app.post("/auth/keys/revoke")
    def post_auth_keys_revoke(body: RevokeKeyRequest):
        revoked = key_service.revoke_key(body.key)
        if not revoked:
            raise HTTPException(status_code=404, detail={"error": "key_not_found"})
        return {"revoked": True}

    return app


def run_api(assistant: AssistantCore, host: str = "127.0.0.1", port: int = 8000):
    """Entry point mirroring run_qml_ui(assistant) — same shared instance,
    different frontend. uvicorn is imported lazily so importing this
    module (e.g. from tests, or from api.py's create_app() call) never
    requires it unless this function is actually called."""
    import uvicorn
    app = create_app(assistant)
    uvicorn.run(app, host=host, port=port)
