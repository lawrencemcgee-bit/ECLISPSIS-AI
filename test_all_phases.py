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

# Must be set before any AudioService is constructed (below, when phase
# test classes import src.core.assistant_core / src.services.audio_service).
# A test suite must never depend on or exercise real hardware — the crash
# this specifically prevents is documented in audio_service.py's
# FORCE_SIMULATED_AUDIO comment.
os.environ["ECLIPSIS_FORCE_SIMULATED_AUDIO"] = "1"
os.environ["ECLIPSIS_FORCE_SIMULATED_VOICE"] = "1"
# Tier 3: same reasoning — VisionService now supports real camera capture
# via cv2.VideoCapture, which must never be exercised by the test suite.
os.environ["ECLIPSIS_FORCE_SIMULATED_VISION"] = "1"

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

    def test_coding_agent_analyzes_python_syntax_error(self):
        """Tier 3: CodingAgent added — real ast-based static analysis,
        never executes the code it's given (see coding_service.py's
        module docstring; SafetyRules permanently blocks
        run_shell_command and this agent never approaches that path)."""
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            broken = assistant.agents.run("coding", action="analyze", code="def f(:\n    pass")
            self.assertFalse(broken.output["valid_syntax"])
            self.assertIn("syntax_error", broken.output)

            clean = assistant.agents.run(
                "coding", action="analyze",
                code="def add(a, b):\n    \"\"\"Add two numbers.\"\"\"\n    return a + b\n",
            )
            self.assertTrue(clean.output["valid_syntax"])
            self.assertEqual(clean.output["function_count"], 1)
            self.assertEqual(clean.output["docstring_coverage_pct"], 100.0)

    def test_coding_agent_diff(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            result = assistant.agents.run(
                "coding", action="diff",
                old_code="a = 1\n", new_code="a = 1\nb = 2\n",
            )
            self.assertEqual(result.output["lines_added"], 1)
            self.assertEqual(result.output["lines_removed"], 0)
            self.assertFalse(result.output["identical"])

    def test_social_agent_analyzes_post_content(self):
        """Tier 3: SocialAgent added — local content analysis only, no
        posting/publishing (no OAuth/API-key infra exists here; see
        social_content_service.py's module docstring)."""
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            result = assistant.agents.run(
                "social", text="Check this out! #cool #stuff", platform="twitter",
            )
            self.assertEqual(result.output["hashtags"], ["#cool", "#stuff"])
            self.assertIn("score", result.output)

            over_limit = assistant.agents.run(
                "social", text="x" * 500, platform="twitter",
            )
            self.assertTrue(over_limit.output["over_limit"])

    def test_creative_agent_generates_headlines_deterministically_with_seed(self):
        """Tier 3: CreativeAgent added — template/procedural generation,
        no LLM (see creative_content_service.py's module docstring)."""
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            r1 = assistant.agents.run("creative", action="headlines", topic="gardening", count=3, seed=7)
            r2 = assistant.agents.run("creative", action="headlines", topic="gardening", count=3, seed=7)
            self.assertEqual(r1.output["headlines"], r2.output["headlines"])
            self.assertEqual(len(r1.output["headlines"]), 3)
            self.assertTrue(all("gardening" in h for h in r1.output["headlines"]))

    def test_creative_agent_writing_prompt_respects_genre(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            result = assistant.agents.run("creative", action="writing_prompt", genre="sci-fi", seed=3)
            self.assertEqual(result.output["genre"], "sci-fi")
            self.assertIn("prompt", result.output)

    def test_creative_agent_outline_known_and_unknown_content_type(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            known = assistant.agents.run("creative", action="outline", topic="x", content_type="how_to_guide")
            self.assertGreater(len(known.output["sections"]), 0)

            unknown = assistant.agents.run("creative", action="outline", topic="x", content_type="not_a_real_type")
            self.assertEqual(unknown.output["sections"], [])
            self.assertIn("note", unknown.output)

    def test_creative_agent_critique_flags_passive_voice_and_cliches(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            text = ("The ball was thrown by John. It was very, very good. "
                     "At the end of the day, it is what it is. "
                     "The ball was thrown. The ball was thrown again.")
            result = assistant.agents.run("creative", action="critique", text=text)
            self.assertGreaterEqual(result.output["passive_voice_count"], 3)
            self.assertIn("at the end of the day", result.output["cliches_found"])
            self.assertTrue(len(result.output["suggestions"]) > 0)


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
        """Phase 8 shipped NCIService as a stub returning
        {"interpreted": text} unconditionally. Tier 3 replaced it with a
        real local heuristic scorer (src/services/nci_service.py), so this
        now checks the real result shape instead of the stub's fixed dict —
        events-fired behavior is unchanged."""
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            fired = []
            assistant.events.on("nci.analysis.started", lambda p: fired.append("started"))
            assistant.events.on("nci.analysis.completed", lambda p: fired.append("completed"))

            result = assistant.analyze("summarize my day")
            self.assertIn("score", result)
            self.assertIn("label", result)
            self.assertIn("breakdown", result)
            self.assertEqual(fired, ["started", "completed"])

    def test_analyze_scores_quality_without_topic(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            substantial = (
                "Researchers published a new study today. According to the "
                "report, the survey data shows a significant shift in how "
                "people consume media online. " * 15
            )
            result = assistant.analyze(substantial)
            self.assertGreater(result["score"], 0)
            self.assertIn("quality", result["breakdown"])
            self.assertNotIn("relevance", result["breakdown"])

    def test_analyze_scores_relevance_with_topic(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            content = "Solar panels and battery storage are transforming home energy. " * 10
            on_topic = assistant.analyze(content, topic="solar energy storage")
            off_topic = assistant.analyze(content, topic="medieval castle architecture")

            self.assertIn("relevance", on_topic["breakdown"])
            self.assertGreater(
                on_topic["breakdown"]["relevance"]["score"],
                off_topic["breakdown"]["relevance"]["score"],
            )

    def test_analyze_reports_fetch_failure_without_raising(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            result = assistant.analyze(url="http://this-domain-does-not-exist.invalid/article")
            self.assertEqual(result["label"], "unscoreable")
            self.assertIn("reason", result)

    def test_analyze_persists_and_get_latest_returns_recent_first(self):
        """Tier 3: NCI reports are now persisted (PersistenceService) and
        retrievable via get_latest_nci_reports() — batch/persistence
        endpoints backing this were the whole point of this addition."""
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            assistant.analyze("first report")
            assistant.analyze("second report, somewhat longer than the first one")

            latest = assistant.get_latest_nci_reports(limit=5)
            self.assertEqual(len(latest), 2)
            self.assertIn("timestamp", latest[0])
            self.assertIn("result", latest[0])
            # Most recent first — the second (longer) call was scored last.
            self.assertGreater(
                latest[0]["result"]["stats"]["word_count"],
                latest[1]["result"]["stats"]["word_count"],
            )

    def test_analyze_history_survives_across_instances(self):
        """Persistence, not just an in-memory list — a fresh AssistantCore
        pointed at the same working directory should see prior history."""
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant1 = AssistantCore()
            assistant1.analyze("persisted report")

            assistant2 = AssistantCore()
            latest = assistant2.get_latest_nci_reports()
            self.assertEqual(len(latest), 1)

    def test_analyze_history_is_capped(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            for i in range(assistant.MAX_HISTORY_ENTRIES + 10):
                assistant.analyze(f"report {i}")
            self.assertEqual(len(assistant._nci_reports), assistant.MAX_HISTORY_ENTRIES)

    def test_analyze_batch_scores_each_item(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            results = assistant.analyze_batch([
                {"text": "first item"},
                {"text": "second item", "topic": "second"},
            ])
            self.assertEqual(len(results), 2)
            self.assertIn("relevance", results[1]["breakdown"])
            self.assertNotIn("relevance", results[0]["breakdown"])

    def test_analyze_batch_rejects_empty_and_oversized(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            with self.assertRaises(ValueError):
                assistant.analyze_batch([])
            with self.assertRaises(ValueError):
                assistant.analyze_batch([{"text": "x"}] * (assistant.MAX_BATCH_SIZE + 1))

    def test_vision_capture_persists_and_get_latest_returns_recent_first(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            assistant.grant_permission("access_camera")
            assistant.capture_vision()
            assistant.capture_vision()

            latest = assistant.get_latest_vision_captures(limit=5)
            self.assertEqual(len(latest), 2)
            self.assertIn("timestamp", latest[0])
            self.assertIn("result", latest[0])

    def test_vision_capture_denied_permission_not_recorded(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            assistant.deny_permission("access_camera")
            result = assistant.capture_vision()
            self.assertIsNone(result)
            self.assertEqual(assistant.get_latest_vision_captures(), [])

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
            # wired up. Voice/Audio/Vision all now depend on whether real
            # capture is actually available in THIS environment (a Vosk
            # model present, PortAudio installed, a camera opened, etc.)
            # — real capture made these environment-dependent, so
            # "simulated" must be checked against actual availability
            # rather than hardcoded True the way this assertion
            # originally checked vision (written before real capture
            # existed for it; a user running this suite with a real
            # camera working correctly would hit this exact stale
            # assumption failing). The test suite forces all three to
            # simulated via ECLIPSIS_FORCE_SIMULATED_* (see top of file),
            # so these should all read True here regardless of the host
            # machine's actual hardware.
            self.assertEqual(
                snapshot["subsystems"]["vision"]["simulated"],
                not assistant.vision.camera_available,
            )
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
        """Tier 3: every route now requires an API key (see
        src/api/api_key_service.py). Attaching a valid one here, once,
        means every existing test below keeps working unchanged — auth
        itself is exercised separately in
        Phase11bApiKeyAuthentication below, including the
        no-key/wrong-key/bootstrap-key paths this helper deliberately
        doesn't cover."""
        from src.core.assistant_core import AssistantCore
        from src.api.api_app import create_app
        from src.api.api_key_service import ApiKeyService
        assistant = AssistantCore()
        key_service = ApiKeyService()
        bootstrap_key = key_service.generate_key(label="test")
        app = create_app(assistant, api_keys=key_service)
        client = TestClient(app)
        client.headers.update({"X-API-Key": bootstrap_key})
        return client, assistant

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

    def test_nci_batch_and_latest_endpoints(self):
        """Tier 3: /nci/batch and /nci/latest moved out of the 501 list —
        AssistantCore.analyze_batch()/get_latest_nci_reports() back them
        for real now, with persisted history. No general 501-stub test
        remains since every originally-stubbed endpoint now has a real
        backing implementation; the _not_implemented() helper itself
        stays in api_app.py for any future endpoint that doesn't."""
        with _isolated_cwd():
            client, assistant = self._client()
            resp = client.post("/nci/batch", json={"items": [
                {"text": "Short piece one."},
                {"text": "Short piece two, with quite a bit more length added to it."},
            ]})
            self.assertEqual(resp.status_code, 200)
            results = resp.json()["results"]
            self.assertEqual(len(results), 2)

            latest = client.get("/nci/latest").json()["reports"]
            self.assertEqual(len(latest), 2)
            # Most recent first: the second (longer) text was scored last.
            self.assertGreater(
                latest[0]["result"]["stats"]["word_count"],
                latest[1]["result"]["stats"]["word_count"],
            )

    def test_nci_batch_rejects_oversized_batch(self):
        with _isolated_cwd():
            client, assistant = self._client()
            items = [{"text": "x"}] * (assistant.MAX_BATCH_SIZE + 5)
            resp = client.post("/nci/batch", json={"items": items})
            self.assertEqual(resp.status_code, 422)

    def test_vision_latest_endpoint_returns_history(self):
        with _isolated_cwd():
            client, assistant = self._client()
            assistant.grant_permission("access_camera")
            client.post("/vision/analyze")
            client.post("/vision/analyze")

            latest = client.get("/vision/latest").json()["captures"]
            self.assertEqual(len(latest), 2)
            self.assertIn("timestamp", latest[0])
            self.assertIn("result", latest[0])

    def test_social_analyze_endpoint(self):
        with _isolated_cwd():
            client, assistant = self._client()
            resp = client.post("/social/analyze", json={"text": "Hi #test", "platform": "twitter"})
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json()["result"]["hashtags"], ["#test"])

    def test_coding_analyze_endpoint(self):
        with _isolated_cwd():
            client, assistant = self._client()
            resp = client.post("/coding/analyze", json={"code": "def f(:\n    pass"})
            self.assertEqual(resp.status_code, 200)
            self.assertFalse(resp.json()["result"]["valid_syntax"])

    def test_coding_diff_endpoint(self):
        with _isolated_cwd():
            client, assistant = self._client()
            resp = client.post("/coding/diff", json={"old_code": "a = 1\n", "new_code": "a = 2\n"})
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json()["result"]["lines_added"], 1)
            self.assertEqual(resp.json()["result"]["lines_removed"], 1)

    def test_creative_headlines_endpoint(self):
        with _isolated_cwd():
            client, assistant = self._client()
            resp = client.post("/creative/headlines", json={"topic": "coffee", "count": 3, "seed": 1})
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(len(resp.json()["result"]["headlines"]), 3)

    def test_creative_prompt_endpoint(self):
        with _isolated_cwd():
            client, assistant = self._client()
            resp = client.post("/creative/prompt", json={"genre": "fantasy", "seed": 2})
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json()["result"]["genre"], "fantasy")

    def test_creative_outline_endpoint(self):
        with _isolated_cwd():
            client, assistant = self._client()
            resp = client.post("/creative/outline", json={"topic": "coffee", "content_type": "listicle"})
            self.assertEqual(resp.status_code, 200)
            self.assertGreater(len(resp.json()["result"]["sections"]), 0)

    def test_creative_critique_endpoint(self):
        with _isolated_cwd():
            client, assistant = self._client()
            resp = client.post("/creative/critique", json={"text": "It was very, very good."})
            self.assertEqual(resp.status_code, 200)
            self.assertIn("suggestions", resp.json()["result"])


@unittest.skipUnless(_FASTAPI_AVAILABLE, "fastapi/httpx not installed in this environment")
class Phase11bApiKeyAuthentication(unittest.TestCase):
    """Tier 3: fixes Milestone 11's known limitation that anything
    reaching the port could call every route (see
    docs/milestone_11_report.md). Deliberately separate from
    Phase11CrossPlatformAPI, whose _client() helper attaches a valid key
    so the rest of that class can focus on endpoint behavior rather than
    re-proving auth on every single test."""

    def _app_and_assistant(self):
        from src.core.assistant_core import AssistantCore
        from src.api.api_app import create_app
        from src.api.api_key_service import ApiKeyService
        assistant = AssistantCore()
        key_service = ApiKeyService()
        app = create_app(assistant, api_keys=key_service)
        return app, assistant, key_service

    def test_request_without_key_is_401(self):
        with _isolated_cwd():
            app, assistant, key_service = self._app_and_assistant()
            client = TestClient(app)
            resp = client.get("/diagnostics")
            self.assertEqual(resp.status_code, 401)

    def test_request_with_wrong_key_is_401(self):
        with _isolated_cwd():
            app, assistant, key_service = self._app_and_assistant()
            client = TestClient(app)
            client.headers.update({"X-API-Key": "not-a-real-key"})
            resp = client.get("/diagnostics")
            self.assertEqual(resp.status_code, 401)

    def test_first_run_bootstrap_key_is_generated_and_works(self):
        """Creating the app with no pre-existing keys must generate one
        (has_any_key() was False) and that exact key — captured from the
        stderr print, the only channel it's ever exposed on — must
        authenticate."""
        import contextlib
        import io
        import re
        with _isolated_cwd():
            from src.core.assistant_core import AssistantCore
            from src.api.api_app import create_app
            from src.api.api_key_service import ApiKeyService
            assistant = AssistantCore()
            key_service = ApiKeyService()
            self.assertFalse(key_service.has_any_key())

            captured = io.StringIO()
            with contextlib.redirect_stderr(captured):
                app = create_app(assistant, api_keys=key_service)
            self.assertTrue(key_service.has_any_key())

            match = re.search(r"^\s{4}(\S+)\s*$", captured.getvalue(), re.MULTILINE)
            self.assertIsNotNone(match, "bootstrap key not found in stderr output")
            bootstrap_key = match.group(1)

            client = TestClient(app)
            client.headers.update({"X-API-Key": bootstrap_key})
            resp = client.get("/diagnostics")
            self.assertEqual(resp.status_code, 200)

    def test_valid_key_authenticates(self):
        with _isolated_cwd():
            app, assistant, key_service = self._app_and_assistant()
            raw_key = key_service.generate_key(label="test-client")
            client = TestClient(app)
            client.headers.update({"X-API-Key": raw_key})
            resp = client.get("/diagnostics")
            self.assertEqual(resp.status_code, 200)

    def test_revoked_key_stops_authenticating(self):
        with _isolated_cwd():
            app, assistant, key_service = self._app_and_assistant()
            raw_key = key_service.generate_key(label="temp")
            client = TestClient(app)
            client.headers.update({"X-API-Key": raw_key})
            self.assertEqual(client.get("/diagnostics").status_code, 200)

            self.assertTrue(key_service.revoke_key(raw_key))
            self.assertEqual(client.get("/diagnostics").status_code, 401)

    def test_auth_keys_endpoint_creates_and_lists_redacted(self):
        with _isolated_cwd():
            app, assistant, key_service = self._app_and_assistant()
            raw_key = key_service.generate_key(label="admin")
            client = TestClient(app)
            client.headers.update({"X-API-Key": raw_key})

            resp = client.post("/auth/keys", json={"label": "mobile-app"})
            self.assertEqual(resp.status_code, 200)
            new_key = resp.json()["key"]
            self.assertTrue(new_key)

            listing = client.get("/auth/keys").json()
            labels = [k["label"] for k in listing]
            self.assertIn("mobile-app", labels)
            self.assertIn("admin", labels)
            # Redacted: no entry exposes the raw key or its hash.
            for entry in listing:
                self.assertEqual(set(entry.keys()), {"label"})

    def test_auth_keys_revoke_endpoint(self):
        with _isolated_cwd():
            app, assistant, key_service = self._app_and_assistant()
            raw_key = key_service.generate_key(label="admin")
            other_key = key_service.generate_key(label="disposable")
            client = TestClient(app)
            client.headers.update({"X-API-Key": raw_key})

            resp = client.post("/auth/keys/revoke", json={"key": other_key})
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(resp.json()["revoked"])

            # The revoked key can no longer authenticate.
            other_client = TestClient(app)
            other_client.headers.update({"X-API-Key": other_key})
            self.assertEqual(other_client.get("/diagnostics").status_code, 401)

    def test_lockout_self_heals_on_restart(self):
        """If every key is revoked, the NEXT create_app() call (a server
        restart, in practice) must regenerate a bootstrap key rather than
        leaving the operator permanently locked out."""
        with _isolated_cwd():
            app, assistant, key_service = self._app_and_assistant()
            for entry in list(key_service._keys.keys()):
                del key_service._keys[entry]
            key_service._save()
            self.assertFalse(key_service.has_any_key())

            from src.api.api_app import create_app
            create_app(assistant, api_keys=key_service)
            self.assertTrue(key_service.has_any_key())


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

    def test_sequence_action_runs_steps_in_order(self):
        """Tier 3: multi-step automation actions — a "sequence" action
        runs its steps through the same _execute_automation_action()
        dispatch as any single action, so each step already has whatever
        verification/permission checks that action type has on its own."""
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            order = []
            assistant.events.on("automation.notification", lambda p: order.append(p["text"]))

            result = assistant._execute_automation_action({
                "type": "sequence",
                "steps": [
                    {"type": "notify", "text": "first"},
                    {"type": "notify", "text": "second"},
                    {"type": "notify", "text": "third"},
                ],
            })
            self.assertEqual(order, ["first", "second", "third"])
            self.assertTrue(result["all_ok"])
            self.assertEqual(result["steps_run"], 3)
            self.assertEqual(result["steps_total"], 3)

    def test_sequence_action_stops_on_error_by_default(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            result = assistant._execute_automation_action({
                "type": "sequence",
                "steps": [
                    {"type": "notify", "text": "ok"},
                    {"type": "not_a_real_type"},
                    {"type": "notify", "text": "never reached"},
                ],
            })
            self.assertFalse(result["all_ok"])
            self.assertEqual(result["steps_run"], 2)  # stopped after the failure
            self.assertEqual(result["steps_total"], 3)
            self.assertTrue(result["steps"][0]["ok"])
            self.assertFalse(result["steps"][1]["ok"])

    def test_sequence_action_continues_on_error_when_configured(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            order = []
            assistant.events.on("automation.notification", lambda p: order.append(p["text"]))

            result = assistant._execute_automation_action({
                "type": "sequence",
                "stop_on_error": False,
                "steps": [
                    {"type": "notify", "text": "ok"},
                    {"type": "not_a_real_type"},
                    {"type": "notify", "text": "still runs"},
                ],
            })
            self.assertEqual(order, ["ok", "still runs"])
            self.assertFalse(result["all_ok"])
            self.assertEqual(result["steps_run"], 3)

    def test_sequence_action_can_nest(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            result = assistant._execute_automation_action({
                "type": "sequence",
                "steps": [
                    {"type": "sequence", "steps": [{"type": "notify", "text": "nested"}]},
                ],
            })
            self.assertTrue(result["all_ok"])
            self.assertTrue(result["steps"][0]["result"]["all_ok"])

    def test_sequence_action_nested_failure_propagates_all_ok_upward(self):
        """A nested sequence can return normally (no exception) while
        reporting its OWN all_ok: False. The parent must reflect that in
        its own all_ok/step "ok" rather than reporting success just
        because nothing raised at its level."""
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            result = assistant._execute_automation_action({
                "type": "sequence",
                "steps": [{
                    "type": "sequence", "stop_on_error": False,
                    "steps": [{"type": "not_a_real_type"}],
                }],
            })
            self.assertFalse(result["all_ok"])
            self.assertFalse(result["steps"][0]["ok"])

    def test_sequence_action_enforces_depth_limit(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            action = {"type": "notify", "text": "deepest"}
            for _ in range(assistant.MAX_SEQUENCE_DEPTH + 3):
                action = {"type": "sequence", "steps": [action]}
            result = assistant._execute_automation_action(action)
            self.assertFalse(result["all_ok"])  # depth violation surfaces, doesn't crash

    def test_sequence_action_enforces_step_count_limit(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            too_many = [{"type": "notify", "text": "x"}] * (assistant.MAX_SEQUENCE_STEPS + 5)
            with self.assertRaises(ValueError):
                assistant._execute_automation_action({"type": "sequence", "steps": too_many})

    def test_sequence_action_rejects_empty_steps(self):
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            with self.assertRaises(ValueError):
                assistant._execute_automation_action({"type": "sequence", "steps": []})

    def test_sequence_action_works_as_a_registered_schedule_trigger(self):
        """End-to-end: a sequence works the same way through the normal
        trigger -> tick -> _fire -> executor path as any other action
        type, not just when called directly."""
        from src.core.assistant_core import AssistantCore
        with _isolated_cwd():
            assistant = AssistantCore()
            completed = []
            assistant.events.on("automation.completed", lambda p: completed.append(p))

            assistant.register_schedule_automation(
                interval_seconds=60,
                action={
                    "type": "sequence",
                    "steps": [
                        {"type": "notify", "text": "a"},
                        {"type": "agent", "agent": "weather", "kwargs": {"location": "Austin"}},
                    ],
                },
                run_immediately=True,
            )
            assistant.automation_tick()

            self.assertEqual(len(completed), 1)
            self.assertTrue(completed[0]["result"]["all_ok"])

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
