"""
Cross-platform HTTP API (Phase 11) — exposes AssistantCore over FastAPI so
a future mobile client, browser client, or any other frontend can talk to
the SAME assistant instance as the desktop QML UI, instead of each
frontend needing its own separate core. This is the same "one shared
instance" principle Phase 2 fixed for the desktop bootstrap
(run.py / qml_app.py) — see create_app()'s docstring.

Endpoints implemented here cover only capabilities that actually exist
elsewhere in the codebase (process_message, analyze, capture_vision,
plugins, diagnostics, permissions). Endpoints named in the original design
prompt but backed by functionality that doesn't exist yet — batch NCI
scoring, social-media ingestion, latest-report history — return
501 Not Implemented with an explanatory body instead of either faking a
result or silently omitting the route. A client hitting them gets a
clear, typed answer instead of a generic 404.

Permission endpoints (/permissions, /permissions/grant|deny|revoke)
weren't in the original endpoint list, but a remote client has no other
way to satisfy Phase 10's fail-closed default for camera/mic access —
without them, /vision/analyze would 403 forever with no way to resolve it
from outside the process.
"""

import dataclasses

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.core.assistant_core import AssistantCore


class MessageRequest(BaseModel):
    message: str


class NCIScoreRequest(BaseModel):
    text: str


class PluginExecuteRequest(BaseModel):
    payload: dict = {}


class PermissionAction(BaseModel):
    permission: str


def _result_dict(result):
    """AssistantResult/AgentResult/TaskResult (src/core/results.py) are
    plain dataclasses — convert once, consistently, instead of every route
    hand-rolling its own response shape."""
    if dataclasses.is_dataclass(result):
        return dataclasses.asdict(result)
    return result


def _not_implemented(feature: str, reason: str):
    raise HTTPException(status_code=501, detail={"feature": feature, "reason": reason})


def create_app(assistant: AssistantCore) -> FastAPI:
    """Factory, not a module-level app — mirrors run_qml_ui(assistant):
    the caller passes in the ONE shared AssistantCore instance rather than
    this module constructing its own. See /api.py at the repo root for the
    process entry point that does that construction (mirrors run.py)."""
    app = FastAPI(title="ECLIPSIS-AI API", version="0.1.0")
    app.state.assistant = assistant

    @app.post("/message")
    def post_message(body: MessageRequest):
        result = assistant.process_message(body.message)
        return _result_dict(result)

    @app.post("/nci/score")
    def post_nci_score(body: NCIScoreRequest):
        return assistant.analyze(body.text)

    @app.post("/nci/batch")
    def post_nci_batch():
        _not_implemented("nci.batch", "NCIService has no batch-scoring mode yet.")

    @app.get("/nci/latest")
    def get_nci_latest():
        _not_implemented("nci.latest", "NCI reports are not persisted yet — nothing to retrieve.")

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
    def get_vision_latest():
        _not_implemented("vision.latest", "Vision analysis results are not persisted yet.")

    @app.post("/social/analyze")
    def post_social_analyze():
        _not_implemented("social.analyze", "Social-media ingestion has no backing agent yet.")

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

    return app


def run_api(assistant: AssistantCore, host: str = "127.0.0.1", port: int = 8000):
    """Entry point mirroring run_qml_ui(assistant) — same shared instance,
    different frontend. uvicorn is imported lazily so importing this
    module (e.g. from tests, or from api.py's create_app() call) never
    requires it unless this function is actually called."""
    import uvicorn
    app = create_app(assistant)
    uvicorn.run(app, host=host, port=port)
