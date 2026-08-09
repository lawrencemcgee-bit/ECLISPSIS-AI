"""
ECLIPSIS-AI — Cross-Phase Regression Test Script
==================================================

Covers Phases 1-13. Run from the repository root:

    python test_all_phases.py

No extra installs required beyond the project's own dependencies — uses only
the standard library's `unittest`. Does NOT launch the QML UI (no PySide6
required to run this script), so it works even before/without a full GUI
environment set up.

Each phase is its own TestCase so you can also run just one phase, e.g.:

    python -m unittest test_all_phases.Phase3AgentArchitecture -v

Tests run against a temporary, isolated data directory — they never touch
your real data/ folder, and clean up after themselves.
"""

import os
import sys
import ast
import json
import shutil
import tempfile
import time
import unittest

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO_ROOT)


# ---------------------------------------------------------------------------
# Phase 1 — Stabilization
# ---------------------------------------------------------------------------
class Phase1Stabilization(unittest.TestCase):
    def test_no_syntax_errors_in_repo(self):
        """Every .py file in the repo must at least parse."""
        bad = []
        for root, dirs, files in os.walk(REPO_ROOT):
            if ".git" in root or "__pycache__" in root:
                continue
            for f in files:
                if f.endswith(".py"):
                    path = os.path.join(root, f)
                    try:
                        with open(path, encoding="utf-8") as fh:
                            ast.parse(fh.read())
                    except SyntaxError as e:
                        bad.append(f"{path}: line {e.lineno}: {e.msg}")
        self.assertEqual(bad, [], "Syntax errors found:\n" + "\n".join(bad))

    def test_pyproject_toml_is_valid(self):
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib  # py<3.11 fallback, not expected here
        path = os.path.join(REPO_ROOT, "pyproject.toml")
        with open(path, "rb") as f:
            data = tomllib.load(f)
        self.assertIn("project", data)
        self.assertIn("dependencies", data["project"])

    def test_assistant_core_imports_and_instantiates(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            self.assertIsNotNone(assistant)

    def test_conversation_processing_works(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            result = assistant.process_message("Hello assistant")
            self.assertIn("Hello assistant", result.content)


# ---------------------------------------------------------------------------
# Phase 2 — Core Runtime & Event Bus
# ---------------------------------------------------------------------------
class Phase2RuntimeEventBus(unittest.TestCase):
    def test_no_orphaned_dispatcher_present(self):
        """dispatcher.py/events.py were removed in Phase 2 — flag if they've
        crept back in (e.g. from a bad zip merge)."""
        for f in ("src/core/dispatcher.py", "src/core/events.py",
                  "src/tests/test_dispatcher.py"):
            path = os.path.join(REPO_ROOT, f)
            self.assertFalse(
                os.path.exists(path),
                f"{f} should have been removed in Phase 2 — found again. "
                f"Likely a zip was extracted on top of an old folder instead "
                f"of a clean replace."
            )

    def test_event_bus_basic_pubsub(self):
        from src.core.event_bus import EventBus
        bus = EventBus()
        received = []
        bus.on("test.event", lambda payload: received.append(payload))
        bus.emit("test.event", {"ok": True})
        self.assertEqual(received, [{"ok": True}])

    def test_qml_app_run_function_takes_assistant_param(self):
        """Verifies the Phase 2 bootstrap fix (single shared AssistantCore
        instance) without needing to actually launch Qt."""
        import inspect
        try:
            from src.ui.qml_app import run_qml_ui
        except ImportError as e:
            self.skipTest(f"PySide6 not installed in this environment: {e}")
            return
        sig = inspect.signature(run_qml_ui)
        self.assertIn("assistant", sig.parameters,
                       "run_qml_ui() should accept an assistant parameter")


# ---------------------------------------------------------------------------
# Phase 3 — Agent & Tool Architecture
# ---------------------------------------------------------------------------
class Phase3AgentArchitecture(unittest.TestCase):
    def test_agent_execution_success_and_events(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            fired = []
            assistant.events.on("agent.invoked", lambda p: fired.append(("invoked", p)))
            assistant.events.on("agent.completed", lambda p: fired.append(("completed", p)))

            assistant.agents.run("onenote", action="write", page="daily", content="hi")
            result = assistant.agents.run("onenote", action="open", page="daily")
            self.assertEqual(result.output, "hi")

            weather = assistant.agents.run("weather", location="San Antonio")
            self.assertIn("location", weather.output)

            news = assistant.agents.run("news", category="technology")
            self.assertIn("headlines", news.output)

            invoked_count = sum(1 for kind, _ in fired if kind == "invoked")
            completed_count = sum(1 for kind, _ in fired if kind == "completed")
            # 4 calls total: onenote write, onenote open, weather, news
            self.assertEqual(invoked_count, 4)
            self.assertEqual(completed_count, 4)

    def test_agent_failure_path_unregistered_agent(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            fired = []
            assistant.events.on("agent.failed", lambda p: fired.append(p))
            result = assistant.agents.run("nonexistent_agent", foo="bar")
            self.assertIn("error", result.metadata)
            self.assertEqual(len(fired), 1)

    def test_agent_failure_path_missing_kwarg(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            result = assistant.agents.run("onenote", action="open")  # missing 'page'
            self.assertIn("error", result.metadata)


# ---------------------------------------------------------------------------
# Phase 4 — Assistant Core & Orchestration
# ---------------------------------------------------------------------------
class Phase4Orchestration(unittest.TestCase):
    def test_task_failure_path(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            fired = []
            assistant.events.on("task.failed", lambda p: fired.append(p))
            assistant.tasks.start_task("t1", "test task")
            result = assistant.tasks.fail_task("t1", "simulated failure")
            self.assertEqual(result.status, "failed")
            self.assertEqual(result.metadata["error"], "simulated failure")
            self.assertEqual(len(fired), 1)

    def test_plugin_discovery_independent_of_cwd(self):
        """The Phase 4 fix: plugin discovery must not depend on the
        directory the process happened to be launched from."""
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            plugins = assistant.list_plugins()
            plugin_ids = [p["id"] for p in plugins]
            self.assertIn("example_plugin", plugin_ids)

    def test_plugin_execution(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            result = assistant.execute_plugins("example_plugin", "hello")
            self.assertEqual(result["output"], "Processed: hello")

    def test_tool_registry_handles_exceptions_gracefully(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            assistant.tools.register("boom", lambda: 1 / 0)
            result = assistant.tools.run("boom")
            self.assertIn("error", result)
            # existing tool still works
            self.assertEqual(assistant.tools.run("echo", "hi"), {"echo": "hi"})


# ---------------------------------------------------------------------------
# Phase 5 — Memory System
# ---------------------------------------------------------------------------
class Phase5Memory(unittest.TestCase):
    def test_long_term_memory_survives_restart(self):
        """The core claim of Phase 5: long-term memory must persist across
        separate AssistantCore instances (simulating an app restart)."""
        from src.core.assistant_core import AssistantCore
        tmp_dir = tempfile.mkdtemp(prefix="eclipsis_memtest_")
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_dir)

            assistant1 = AssistantCore()
            assistant1.memory.remember_long_term("user_name", "Alex")

            assistant2 = AssistantCore()  # simulates a fresh restart
            self.assertEqual(assistant2.memory.recall_long_term("user_name"), "Alex")
        finally:
            os.chdir(old_cwd)
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_short_term_memory_does_not_survive_restart(self):
        from src.core.assistant_core import AssistantCore
        tmp_dir = tempfile.mkdtemp(prefix="eclipsis_memtest_")
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_dir)

            assistant1 = AssistantCore()
            assistant1.memory.remember("scratch", "not persisted")

            assistant2 = AssistantCore()
            self.assertIsNone(assistant2.memory.recall("scratch"))
        finally:
            os.chdir(old_cwd)
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_memory_json_file_written_correctly(self):
        from src.core.assistant_core import AssistantCore
        import json
        tmp_dir = tempfile.mkdtemp(prefix="eclipsis_memtest_")
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_dir)
            assistant = AssistantCore()
            assistant.memory.remember_long_term("key1", "value1")

            memory_path = os.path.join(tmp_dir, "data", "memory.json")
            self.assertTrue(os.path.exists(memory_path))
            with open(memory_path) as f:
                data = json.load(f)
            self.assertEqual(data["key1"], "value1")
        finally:
            os.chdir(old_cwd)
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_no_deprecation_warnings_in_core_flow(self):
        """Runs the main application flow with warnings captured and asserts
        none fire. Catches things like the datetime.utcnow() deprecation
        found and fixed in logging_service.py during hardening review."""
        import warnings
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                assistant = AssistantCore()
                assistant.process_message("test")
                assistant.agents.run("weather", location="Test City")
                assistant.tasks.start_task("t1", "test")
                assistant.tasks.fail_task("t1", "err")
                assistant.memory.remember_long_term("k", "v")
            unexpected = [str(w.message) for w in caught
                          if issubclass(w.category, DeprecationWarning)]
            self.assertEqual(unexpected, [],
                              "Deprecation warnings found in core flow: " + "; ".join(unexpected))



# ---------------------------------------------------------------------------
# Phase 6 — Multimodal System
# ---------------------------------------------------------------------------
class Phase6Multimodal(unittest.TestCase):
    def test_multimodal_services_owned_by_core(self):
        """Vision/Voice/Audio must be constructed by AssistantCore itself,
        not left orphaned or owned by the UI layer."""
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            self.assertIsNotNone(assistant.vision)
            self.assertIsNotNone(assistant.voice)
            self.assertIsNotNone(assistant.audio)

    def test_toggle_mic_and_events(self):
        """Phase 10 note: turning the mic on is now permission-gated, so
        this test grants access_microphone first — the fail-closed default
        without a grant is covered separately in Phase10Security."""
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            assistant.grant_permission("access_microphone")
            fired = []
            assistant.events.on("audio.started", lambda p: fired.append("started"))
            assistant.events.on("audio.stopped", lambda p: fired.append("stopped"))

            self.assertFalse(assistant.audio.active)
            state = assistant.toggle_mic()
            self.assertTrue(state)
            self.assertTrue(assistant.settings["mic_enabled"])

            state = assistant.toggle_mic()
            self.assertFalse(state)
            self.assertFalse(assistant.settings["mic_enabled"])

            self.assertEqual(fired, ["started", "stopped"])

    def test_mic_state_restored_on_restart(self):
        """The core claim of this phase's audio-ownership move: a restarted
        AssistantCore should resume listening if it was on when settings
        were last saved — previously this restore logic lived only in the
        UI layer's __init__.

        Phase 10 note: access_microphone is granted first since toggle_mic
        is now permission-gated; the grant itself persists too, so
        assistant2 doesn't need to re-grant it."""
        from src.core.assistant_core import AssistantCore
        tmp_dir = tempfile.mkdtemp(prefix="eclipsis_audiotest_")
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_dir)
            assistant1 = AssistantCore()
            assistant1.grant_permission("access_microphone")
            assistant1.toggle_mic()  # turn on
            assistant1.save_settings()

            assistant2 = AssistantCore()  # simulated restart
            self.assertTrue(assistant2.audio.active)
        finally:
            os.chdir(old_cwd)
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_vision_and_voice_events_fire(self):
        """Phase 10 note: capture_vision is now permission-gated, so this
        test grants access_camera first — the fail-closed default without
        a grant is covered separately in Phase10Security."""
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            assistant.grant_permission("access_camera")
            fired = []
            assistant.events.on("vision.captured", lambda p: fired.append("vision"))
            assistant.events.on("voice.listening_started", lambda p: fired.append("voice_start"))
            assistant.events.on("voice.listening_stopped", lambda p: fired.append("voice_stop"))

            assistant.capture_vision()
            assistant.start_voice_listening()
            assistant.stop_voice_listening()

            self.assertEqual(fired, ["vision", "voice_start", "voice_stop"])


# ---------------------------------------------------------------------------
# Phase 7 — Voice System
# ---------------------------------------------------------------------------
class Phase7Voice(unittest.TestCase):
    def test_listening_state_is_idempotent(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            fired = []
            assistant.events.on("voice.listening_started", lambda p: fired.append(1))

            self.assertTrue(assistant.start_voice_listening())
            self.assertTrue(assistant.start_voice_listening())  # no-op, already listening
            self.assertEqual(len(fired), 1, "starting twice should only fire one event")

    def test_voice_command_routes_through_conversation_when_listening(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            assistant.start_voice_listening()
            result = assistant.voice_command_received("hello assistant")
            self.assertIn("hello assistant", result.content)

    def test_voice_command_rejected_when_not_listening(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            fired = []
            assistant.events.on("voice.command_rejected", lambda p: fired.append(p))

            result = assistant.voice_command_received("should be rejected")
            self.assertEqual(result.metadata["error"], "not_listening")
            self.assertEqual(len(fired), 1)


# ---------------------------------------------------------------------------
# Phase 8 — NCI Analytics
# ---------------------------------------------------------------------------
class Phase8NCI(unittest.TestCase):
    def test_nci_owned_by_core(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            self.assertIsNotNone(assistant.nci)

    def test_analyze_fires_start_and_completed_events(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            fired = []
            assistant.events.on("nci.analysis.started", lambda p: fired.append("started"))
            assistant.events.on("nci.analysis.completed", lambda p: fired.append("completed"))

            result = assistant.analyze("summarize my day")
            self.assertEqual(result, {"interpreted": "summarize my day"})
            self.assertEqual(fired, ["started", "completed"])

    def test_analyze_not_wired_into_process_message(self):
        """Deliberate design check, not just a behavior check: analyze()
        must stay a standalone, explicitly-invoked capability. If a future
        change accidentally wires it into process_message() without a
        conscious decision, this test should be updated (not just broken
        silently) to reflect that."""
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            fired = []
            assistant.events.on("nci.analysis.started", lambda p: fired.append(1))

            assistant.process_message("hello")
            self.assertEqual(len(fired), 0,
                              "process_message() should not trigger NCI analysis "
                              "unless that integration is a deliberate, documented change")


# ---------------------------------------------------------------------------
# Phase 9 — Observability & Operations Center
# ---------------------------------------------------------------------------
class Phase9Observability(unittest.TestCase):
    def test_observability_owned_by_core_and_subscribed_early(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            self.assertIsNotNone(assistant.observability)
            # Constructed before other subsystems, so it never misses an
            # event emitted during their setup.
            self.assertGreaterEqual(assistant.observability.uptime_seconds(), 0)

    def test_counters_increment_on_normal_flow(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            assistant.process_message("hello assistant")
            self.assertEqual(
                assistant.observability.counters.get("conversation.processed"), 1
            )
            self.assertIn("state.idle", assistant.observability.counters)

    def test_last_error_recorded_on_agent_failure(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            assistant.agents.run("does_not_exist")
            self.assertIsNotNone(assistant.observability.last_error)
            self.assertEqual(assistant.observability.last_error["event"], "agent.failed")
            self.assertEqual(
                assistant.observability.counters.get("agent.failed"), 1
            )

    def test_diagnostics_snapshot_shape(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            snapshot = assistant.get_diagnostics()

            for key in ("uptime_seconds", "counters", "last_error", "system", "subsystems"):
                self.assertIn(key, snapshot)

            for subsystem in ("engine", "voice", "vision", "audio", "plugins"):
                self.assertIn(subsystem, snapshot["subsystems"])
                self.assertIn("healthy", snapshot["subsystems"][subsystem])

            # Honesty check: placeholder-level subsystems must say so
            # rather than reporting as if real hardware/backends are
            # wired up. Vision has no real pipeline yet and is always
            # simulated. Voice/audio now depend on whether real STT/mic
            # capture are actually available in THIS environment (a Vosk
            # model present, PortAudio installed, etc.) — real voice I/O
            # made these two environment-dependent, so "simulated" must
            # be checked against actual availability rather than
            # hardcoded True the way this assertion originally was
            # (written before real capture existed; a user running this
            # suite with real capture working correctly hit this exact
            # stale assumption failing).
            self.assertTrue(snapshot["subsystems"]["vision"]["simulated"])
            self.assertEqual(
                snapshot["subsystems"]["voice"]["simulated"],
                not assistant.voice.stt_available,
            )
            self.assertEqual(
                snapshot["subsystems"]["audio"]["simulated"],
                not assistant.audio.real_capture_available,
            )

    def test_system_metrics_degrade_gracefully_without_psutil(self):
        from src.core import observability as observability_module
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            original_psutil = observability_module.psutil
            try:
                observability_module.psutil = None
                metrics = assistant.observability.system_metrics()
                self.assertEqual(metrics, {"available": False})
            finally:
                observability_module.psutil = original_psutil

    def test_engine_health_reflects_error_state(self):
        from src.core.assistant_core import AssistantCore
        from src.core.state import AssistantState
        with _isolated_cwd():
            assistant = AssistantCore()
            assistant.state_manager.set(AssistantState.ERROR)
            snapshot = assistant.get_diagnostics()
            self.assertFalse(snapshot["subsystems"]["engine"]["healthy"])


# ---------------------------------------------------------------------------
# Phase 10 — Security & Permissions
# ---------------------------------------------------------------------------
class Phase10Security(unittest.TestCase):
    def test_camera_access_fails_closed_by_default(self):
        """The core Phase 10 fix: no prior grant and no decision handler
        means the request must be denied, not auto-approved."""
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            blocked = []
            assistant.events.on("vision.blocked", lambda p: blocked.append(p))

            result = assistant.capture_vision()
            self.assertIsNone(result)
            self.assertEqual(len(blocked), 1)

    def test_microphone_access_fails_closed_by_default(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            blocked = []
            assistant.events.on("audio.blocked", lambda p: blocked.append(p))

            state = assistant.toggle_mic()
            self.assertFalse(state)
            self.assertFalse(assistant.audio.active)
            self.assertEqual(len(blocked), 1)

    def test_grant_persists_across_restart(self):
        from src.core.assistant_core import AssistantCore
        tmp_dir = tempfile.mkdtemp(prefix="eclipsis_permtest_")
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_dir)
            assistant1 = AssistantCore()
            assistant1.grant_permission("access_camera")

            assistant2 = AssistantCore()  # simulated restart
            self.assertIn("access_camera", assistant2.permissions.granted)
            self.assertIsNotNone(assistant2.capture_vision())
        finally:
            os.chdir(old_cwd)
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_deny_persists_and_can_be_revoked(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            assistant.deny_permission("access_camera")
            self.assertIsNone(assistant.capture_vision())

            assistant.revoke_permission("access_camera")
            self.assertNotIn("access_camera", assistant.permissions.granted)
            self.assertNotIn("access_camera", assistant.permissions.denied)
            # Revoked, not granted — still fails closed until re-decided.
            self.assertIsNone(assistant.capture_vision())

    def test_decision_handler_is_consulted_and_result_persisted(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            calls = []

            def always_approve(permission):
                calls.append(permission)
                return True

            assistant.set_permission_decision_handler(always_approve)
            self.assertIsNotNone(assistant.capture_vision())
            self.assertEqual(calls, ["access_camera"])

            # Second request should use the now-persisted grant rather than
            # consulting the handler again.
            assistant.capture_vision()
            self.assertEqual(calls, ["access_camera"])

    def test_hard_blocked_action_ignores_any_permission(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            assistant.grant_permission("run_shell_command")  # should not help
            self.assertFalse(assistant.verification.verify("run_shell_command", {}))

    def test_safety_rules_are_mutable_at_runtime(self):
        from src.core.safety_rules import SafetyRules
        rules = SafetyRules()

        self.assertTrue(rules.is_allowed("access_camera"))
        rules.block("access_camera")
        self.assertFalse(rules.is_allowed("access_camera"))
        self.assertFalse(rules.requires_permission("access_camera"))  # blocked wins

        rules.unblock("access_camera")
        rules.require_permission("access_camera")
        self.assertTrue(rules.requires_permission("access_camera"))

        rules.allow_without_permission("access_camera")
        self.assertFalse(rules.requires_permission("access_camera"))

    def test_diagnostics_reports_security_subsystem(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            assistant.grant_permission("access_camera")
            snapshot = assistant.get_diagnostics()
            security = snapshot["subsystems"]["security"]
            self.assertEqual(security["granted"], 1)
            self.assertEqual(security["denied"], 0)
            self.assertFalse(security["interactive_handler_wired"])


# ---------------------------------------------------------------------------
# Phase 11 — Cross-Platform API
# ---------------------------------------------------------------------------
try:
    from fastapi.testclient import TestClient
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False


@unittest.skipUnless(_FASTAPI_AVAILABLE, "fastapi/httpx not installed in this environment")
class Phase11CrossPlatformAPI(unittest.TestCase):
    def _client(self):
        from src.core.assistant_core import AssistantCore
        from src.api.api_app import create_app
        assistant = AssistantCore()
        app = create_app(assistant)
        return TestClient(app), assistant

    def test_message_endpoint(self):
        with _isolated_cwd():
            client, assistant = self._client()
            resp = client.post("/message", json={"message": "hello"})
            self.assertEqual(resp.status_code, 200)
            self.assertIn("content", resp.json())

    def test_diagnostics_endpoint_matches_core_shape(self):
        with _isolated_cwd():
            client, assistant = self._client()
            resp = client.get("/diagnostics")
            self.assertEqual(resp.status_code, 200)
            body = resp.json()
            for key in ("uptime_seconds", "counters", "last_error", "system", "subsystems"):
                self.assertIn(key, body)

    def test_vision_endpoint_403_without_permission(self):
        """Confirms Phase 10's fail-closed default is reachable and correct
        over HTTP too, not just through direct AssistantCore calls."""
        with _isolated_cwd():
            client, assistant = self._client()
            resp = client.post("/vision/analyze")
            self.assertEqual(resp.status_code, 403)

    def test_permissions_grant_then_vision_succeeds(self):
        """Also proves there's exactly ONE AssistantCore behind the app —
        the grant from one request is visible to the next."""
        with _isolated_cwd():
            client, assistant = self._client()
            grant_resp = client.post("/permissions/grant", json={"permission": "access_camera"})
            self.assertIn("access_camera", grant_resp.json()["granted"])

            resp = client.post("/vision/analyze")
            self.assertEqual(resp.status_code, 200)
            self.assertIn("result", resp.json())

    def test_plugins_list_endpoint(self):
        with _isolated_cwd():
            client, assistant = self._client()
            resp = client.get("/plugins")
            self.assertEqual(resp.status_code, 200)
            self.assertIsInstance(resp.json(), list)

    def test_unimplemented_endpoints_return_501_not_404_or_fake_data(self):
        with _isolated_cwd():
            client, assistant = self._client()
            cases = (
                ("post", "/nci/batch"),
                ("get", "/nci/latest"),
                ("get", "/vision/latest"),
                ("post", "/social/analyze"),
            )
            for method, path in cases:
                resp = getattr(client, method)(path)
                self.assertEqual(resp.status_code, 501, f"{path} should be 501")
                self.assertIn("feature", resp.json()["detail"])


# ---------------------------------------------------------------------------
# Phase 12 — Automation & Proactive Assistance
# ---------------------------------------------------------------------------
class Phase12Automation(unittest.TestCase):
    def test_event_trigger_fires_notify_action(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            notifications = []
            assistant.events.on("automation.notification", lambda p: notifications.append(p))

            assistant.register_event_automation(
                "state.changed",
                {"type": "notify", "text": "the assistant changed state"},
            )
            assistant.process_message("hello")  # triggers a state.changed cycle

            self.assertTrue(len(notifications) >= 1)
            self.assertEqual(notifications[0]["text"], "the assistant changed state")

    def test_event_trigger_predicate_filters_payload(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            fired = []
            assistant.events.on("automation.triggered", lambda p: fired.append(p))

            assistant.register_event_automation(
                "state.changed",
                {"type": "notify", "text": "only for busy"},
                predicate=lambda payload: payload.get("new") == "busy",
            )
            assistant.process_message("hello")

            # state.changed fires more than once per message (busy -> idle);
            # only the "busy" transition should have matched the predicate.
            matched = [f for f in fired if f["context"].get("new") == "busy"]
            self.assertEqual(len(fired), len(matched))

    def test_schedule_trigger_fires_when_due(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            trigger_id = assistant.register_schedule_automation(
                interval_seconds=60,
                action={"type": "notify", "text": "scheduled check-in"},
                run_immediately=True,
            )
            fired = assistant.automation_tick()
            self.assertIn(trigger_id, fired)

            # Recurring: shouldn't fire again immediately after rescheduling.
            fired_again = assistant.automation_tick()
            self.assertNotIn(trigger_id, fired_again)

    def test_schedule_trigger_not_fired_before_due(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            trigger_id = assistant.register_schedule_automation(
                interval_seconds=3600,
                action={"type": "notify", "text": "too soon"},
            )
            fired = assistant.automation_tick()
            self.assertNotIn(trigger_id, fired)

    def test_disabled_trigger_does_not_fire(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            trigger_id = assistant.register_schedule_automation(
                interval_seconds=60,
                action={"type": "notify", "text": "should not fire"},
                run_immediately=True,
            )
            assistant.set_automation_enabled(trigger_id, False)
            fired = assistant.automation_tick()
            self.assertNotIn(trigger_id, fired)

    def test_agent_action_routes_through_agent_router(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            completed = []
            assistant.events.on("automation.completed", lambda p: completed.append(p))

            assistant.register_schedule_automation(
                interval_seconds=60,
                action={"type": "agent", "agent": "weather", "kwargs": {"location": "Austin"}},
                run_immediately=True,
            )
            assistant.automation_tick()

            self.assertEqual(len(completed), 1)

    def test_unknown_action_type_fires_automation_failed(self):
        """Also confirms the Phase 9/12 integration: an automation failure
        is captured by ObservabilityService's last_error, same as an
        agent failure."""
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            failed = []
            assistant.events.on("automation.failed", lambda p: failed.append(p))

            assistant.register_schedule_automation(
                interval_seconds=60,
                action={"type": "not_a_real_type"},
                run_immediately=True,
            )
            assistant.automation_tick()

            self.assertEqual(len(failed), 1)
            self.assertEqual(assistant.observability.last_error["event"], "automation.failed")
            self.assertEqual(assistant.observability.counters.get("automation.failed"), 1)

    def test_list_and_unregister_triggers(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            trigger_id = assistant.register_schedule_automation(
                interval_seconds=60,
                action={"type": "notify", "text": "x"},
            )
            listed = assistant.list_automations()
            self.assertEqual(len(listed), 1)
            self.assertEqual(listed[0]["id"], trigger_id)
            self.assertNotIn("action", listed[0])  # not JSON-safe/stable, deliberately omitted

            assistant.unregister_automation(trigger_id)
            self.assertEqual(assistant.list_automations(), [])

    def test_diagnostics_reports_automation_subsystem(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            assistant.register_schedule_automation(
                interval_seconds=60, action={"type": "notify", "text": "x"}
            )
            snapshot = assistant.get_diagnostics()
            automation = snapshot["subsystems"]["automation"]
            self.assertEqual(automation["triggers"], 1)
            self.assertEqual(automation["enabled"], 1)


# ---------------------------------------------------------------------------
# Phase 13 — Final Validation (tick() wiring + automation persistence)
# ---------------------------------------------------------------------------
class Phase13FinalValidation(unittest.TestCase):
    def test_persistent_schedule_trigger_survives_restart(self):
        from src.core.assistant_core import AssistantCore
        tmp_dir = tempfile.mkdtemp(prefix="eclipsis_automationtest_")
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_dir)
            assistant1 = AssistantCore()
            trigger_id = assistant1.register_schedule_automation(
                interval_seconds=3600,
                action={"type": "notify", "text": "morning check-in"},
            )  # persistent=True by default for schedule triggers

            assistant2 = AssistantCore()  # simulated restart
            listed = assistant2.list_automations()
            self.assertEqual(len(listed), 1)
            self.assertEqual(listed[0]["id"], trigger_id)
        finally:
            os.chdir(old_cwd)
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_non_persistent_trigger_does_not_survive_restart(self):
        from src.core.assistant_core import AssistantCore
        tmp_dir = tempfile.mkdtemp(prefix="eclipsis_automationtest_")
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_dir)
            assistant1 = AssistantCore()
            assistant1.register_schedule_automation(
                interval_seconds=60,
                action={"type": "notify", "text": "one-off"},
                persistent=False,
            )
            assistant2 = AssistantCore()
            self.assertEqual(assistant2.list_automations(), [])
        finally:
            os.chdir(old_cwd)
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_persistent_event_trigger_survives_and_still_fires(self):
        from src.core.assistant_core import AssistantCore
        tmp_dir = tempfile.mkdtemp(prefix="eclipsis_automationtest_")
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_dir)
            assistant1 = AssistantCore()
            assistant1.register_event_automation(
                "state.changed",
                {"type": "notify", "text": "still here after restart"},
                persistent=True,
            )

            assistant2 = AssistantCore()  # simulated restart
            notifications = []
            assistant2.events.on("automation.notification", lambda p: notifications.append(p))
            assistant2.process_message("hello")
            self.assertTrue(len(notifications) >= 1)
        finally:
            os.chdir(old_cwd)
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_event_trigger_with_predicate_cannot_be_persistent(self):
        """The Phase 13 decision made explicit: predicates can't survive a
        restart, so asking for both raises instead of silently dropping
        the predicate."""
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            with self.assertRaises(ValueError):
                assistant.register_event_automation(
                    "state.changed",
                    {"type": "notify", "text": "x"},
                    predicate=lambda payload: True,
                    persistent=True,
                )

    def test_ticker_calls_tick_periodically(self):
        """The actual tick() wiring decision: a background thread started
        by start_automation_ticker(), not left for a UI framework to own."""
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            completed = []
            assistant.events.on("automation.completed", lambda p: completed.append(p))
            assistant.register_schedule_automation(
                interval_seconds=0.05,
                action={"type": "notify", "text": "tick test"},
                run_immediately=True,
                persistent=False,
            )
            try:
                assistant.start_automation_ticker(interval_seconds=0.05)
                time.sleep(0.3)
            finally:
                assistant.stop_automation_ticker()

            self.assertGreaterEqual(len(completed), 1)

    def test_ticker_start_is_idempotent(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            assistant.start_automation_ticker(interval_seconds=5)
            first_thread = assistant._ticker_thread
            assistant.start_automation_ticker(interval_seconds=5)
            second_thread = assistant._ticker_thread
            try:
                self.assertIsNot(first_thread, second_thread)
                self.assertFalse(first_thread.is_alive())
                self.assertTrue(second_thread.is_alive())
            finally:
                assistant.stop_automation_ticker()

    def test_architecture_baseline_reflects_current_state(self):
        """Regression guard: docs/architecture_baseline.md described an
        empty repository all the way through Milestone 8's work — this
        catches it going stale like that again."""
        path = os.path.join(REPO_ROOT, "docs", "architecture_baseline.md")
        with open(path) as f:
            content = f.read()
        self.assertNotIn("repository currently contains only a README", content)

    def test_all_milestone_reports_present(self):
        for n in range(9, 14):
            path = os.path.join(REPO_ROOT, "docs", f"milestone_{n}_report.md")
            self.assertTrue(os.path.exists(path), f"missing milestone_{n}_report.md")


# ---------------------------------------------------------------------------
# Real Voice I/O — post-roadmap work (not part of the original Phases 0-13;
# see docs/voice_io_assessment.md). Real STT (Vosk) / TTS (pyttsx3) /
# real mic capture (sounddevice) are all optional at runtime — most of
# these tests exercise the graceful-degradation contract directly, since
# none of those three packages/a Vosk model are expected to be present in
# every environment this suite runs in.
# ---------------------------------------------------------------------------
class RealVoiceIO(unittest.TestCase):
    def test_audio_service_degrades_gracefully(self):
        from src.services.audio_service import AudioService
        audio = AudioService()
        audio.start()  # must not raise even if sounddevice/PortAudio aren't available
        samples = audio.get_samples()
        self.assertEqual(len(samples), 64)
        audio.stop()

    def test_audio_pop_transcription_empty_without_real_capture(self):
        from src.services.audio_service import AudioService
        audio = AudioService()
        if audio.real_capture_available:
            self.skipTest("real audio capture available in this environment — this checks the no-capture path")
        self.assertEqual(audio.pop_transcription_audio(), b"")

    def test_voice_service_degrades_gracefully_without_stt_or_tts(self):
        from src.services.voice_service import VoiceService
        voice = VoiceService(model_path="/nonexistent/path/so/stt_available/is/false")
        self.assertFalse(voice.stt_available)
        self.assertIsNone(voice.transcribe_chunk(b"\x00\x00" * 100))
        self.assertEqual(voice.list_voices(), [])
        # speak() either genuinely works (pyttsx3 installed) or returns
        # False — either way it must not raise.
        result = voice.speak("hello")
        self.assertIn(result, (True, False))

    def test_transcribe_chunk_parses_final_result(self):
        """Tests the actual glue logic (JSON parsing, text extraction)
        against a fake recognizer, independent of whether the real vosk
        package is installed in this environment."""
        from src.services.voice_service import VoiceService
        voice = VoiceService(model_path="/nonexistent")
        voice.stt_available = True
        voice._recognizer = _FakeRecognizer(accept=True, text="hello nova")
        self.assertEqual(voice.transcribe_chunk(b"\x00\x00"), "hello nova")

    def test_transcribe_chunk_returns_none_for_partial_utterance(self):
        from src.services.voice_service import VoiceService
        voice = VoiceService(model_path="/nonexistent")
        voice.stt_available = True
        voice._recognizer = _FakeRecognizer(accept=False, text="should not be returned")
        self.assertIsNone(voice.transcribe_chunk(b"\x00\x00"))

    def test_transcribe_chunk_returns_none_for_empty_text(self):
        from src.services.voice_service import VoiceService
        voice = VoiceService(model_path="/nonexistent")
        voice.stt_available = True
        voice._recognizer = _FakeRecognizer(accept=True, text="")
        self.assertIsNone(voice.transcribe_chunk(b"\x00\x00"))

    def test_process_voice_audio_noop_when_not_listening(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            assistant.audio.active = True  # simulate capture already running
            self.assertIsNone(assistant.process_voice_audio())

    def test_process_voice_audio_noop_when_audio_inactive(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            assistant.start_voice_listening()
            self.assertFalse(assistant.audio.active)
            self.assertIsNone(assistant.process_voice_audio())

    def test_process_voice_audio_routes_recognized_text_through_existing_pipeline(self):
        """Confirms the actual integration: a fake recognizer producing
        text ends up routed through voice_command_received() ->
        process_message(), the same tested pipeline typed messages use."""
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            assistant.audio.active = True
            assistant.audio.real_capture_available = True
            assistant.audio._pending_frames = [b"\x00\x00"]
            assistant.start_voice_listening()
            assistant.voice.stt_available = True
            assistant.voice._recognizer = _FakeRecognizer(accept=True, text="hello assistant")

            outcome = assistant.process_voice_audio()
            self.assertIsNotNone(outcome)
            self.assertEqual(outcome["text"], "hello assistant")
            self.assertIsNotNone(outcome["result"].content)

    def test_diagnostics_reports_stt_tts_capture_availability(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            snapshot = assistant.get_diagnostics()
            voice = snapshot["subsystems"]["voice"]
            audio = snapshot["subsystems"]["audio"]
            for key in ("stt_available", "tts_available", "simulated"):
                self.assertIn(key, voice)
            self.assertIn("simulated", audio)


class _FakeRecognizer:
    """Stands in for vosk.KaldiRecognizer's two relevant methods, so the
    glue logic in VoiceService.transcribe_chunk() can be tested without
    the real vosk package or a downloaded model."""
    def __init__(self, accept: bool, text: str):
        self._accept = accept
        self._text = text

    def AcceptWaveform(self, audio_bytes):
        return self._accept

    def Result(self):
        return json.dumps({"text": self._text})


# ---------------------------------------------------------------------------
# Dependency / environment checks
# ---------------------------------------------------------------------------
class DependencyChecks(unittest.TestCase):
    def test_pyproject_has_no_known_bad_pins(self):
        """Regression guard against reintroducing versions already confirmed
        broken or vulnerable on Python 3.13 (PySide6 6.7.x, pydantic 2.7.1,
        fastapi 0.110.0, requests 2.31.0, orjson 3.10.0, etc.)."""
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib
        path = os.path.join(REPO_ROOT, "pyproject.toml")
        with open(path, "rb") as f:
            data = tomllib.load(f)
        deps = {d.split("==")[0].split(">=")[0]: d for d in data["project"]["dependencies"]}

        known_bad = {
            "pyside6": "6.7.2",
            "pydantic": "2.7.1",
            "fastapi": "0.110.0",
            "uvicorn": "0.29.0",
            "mypy": "1.10.0",
            "requests": "2.31.0",
            "orjson": "3.10.0",
        }
        for pkg, bad_version in known_bad.items():
            self.assertIn(pkg, deps, f"{pkg} missing from pyproject.toml entirely")
            self.assertNotIn(f"=={bad_version}", deps[pkg],
                              f"{pkg} is pinned back to the known-bad {bad_version}")

    def test_requires_python_has_upper_bound(self):
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib
        path = os.path.join(REPO_ROOT, "pyproject.toml")
        with open(path, "rb") as f:
            data = tomllib.load(f)
        req = data["project"]["requires-python"]
        self.assertIn("<", req,
                      "requires-python should have an upper bound (see Phase 2 "
                      "dependency audit) to avoid this exact class of bug "
                      "recurring on a future Python version")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
class _isolated_cwd:
    """Context manager: run a block inside a fresh temp directory so
    PersistenceService/SessionStateService/etc. don't read or write your
    real data/ folder, and clean up afterward."""

    def __enter__(self):
        self._tmp_dir = tempfile.mkdtemp(prefix="eclipsis_test_")
        self._old_cwd = os.getcwd()
        os.chdir(self._tmp_dir)
        return self._tmp_dir

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.chdir(self._old_cwd)
        shutil.rmtree(self._tmp_dir, ignore_errors=True)
        return False


if __name__ == "__main__":
    unittest.main(verbosity=2)
