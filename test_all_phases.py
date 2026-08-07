"""
ECLIPSIS-AI — Cross-Phase Regression Test Script
==================================================

Covers Phases 1-5. Run from the repository root:

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
import shutil
import tempfile
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
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
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
        UI layer's __init__."""
        from src.core.assistant_core import AssistantCore
        tmp_dir = tempfile.mkdtemp(prefix="eclipsis_audiotest_")
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_dir)
            assistant1 = AssistantCore()
            assistant1.toggle_mic()  # turn on
            assistant1.save_settings()

            assistant2 = AssistantCore()  # simulated restart
            self.assertTrue(assistant2.audio.active)
        finally:
            os.chdir(old_cwd)
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_vision_and_voice_events_fire(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
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
