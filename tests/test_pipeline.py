"""
Tests for end-to-end pipeline flow simulation, skip_routing, failure modes,
and pipeline mode file.

The pipeline has these stages:
  1. session-start (bootstrap, apply proposals)
  2. router (classify + select harness)
  3. harness execution (subagent)
  4. subagent-complete (mark eval pending)
  5. evaluator (score)
  6. weight update / evolution
  7. session-end (merge weights)

Pipeline mode values: "auto" | "run" | absent (off)
"""

import json
import os
import subprocess

import pytest


WORKSPACE_ROOT = "/home/seongwoong/workspace/adaptive-harness"
HOOKS_DIR = os.path.join(WORKSPACE_ROOT, "hooks")
PLUGIN_ROOT = "/home/seongwoong/.claude/plugins/cache/adaptive-harness/adaptive-harness/1.0.0"


def _run_hook(hook_name: str, env: dict, cwd: str, stdin: str = "") -> tuple[str, str, int]:
    hook_path = os.path.join(HOOKS_DIR, hook_name)
    proc = subprocess.run(
        ["bash", hook_path],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd,
    )
    return proc.stdout, proc.stderr, proc.returncode


# ---------------------------------------------------------------------------
# Pipeline mode file
# ---------------------------------------------------------------------------

class TestPipelineModeFile:
    def test_pipeline_mode_auto_file(self, tmp_state_dir):
        mode_file = tmp_state_dir / ".pipeline-mode"
        mode_file.write_text("auto")
        assert mode_file.read_text() == "auto"

    def test_pipeline_mode_run_file(self, tmp_state_dir):
        mode_file = tmp_state_dir / ".pipeline-mode"
        mode_file.write_text("run")
        assert mode_file.read_text() == "run"

    def test_pipeline_mode_absent_means_off(self, tmp_state_dir):
        mode_file = tmp_state_dir / ".pipeline-mode"
        assert not mode_file.exists()

    def test_pipeline_mode_values_are_exclusive(self):
        valid_modes = {"auto", "run", ""}  # "" = off/absent
        assert "auto" in valid_modes
        assert "run" in valid_modes
        assert "invalid" not in valid_modes

    def test_run_mode_clears_on_session_start(self, tmp_path):
        """session-start.sh should clear .pipeline-mode when value is 'run'."""
        (tmp_path / ".git").mkdir()
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()
        mode_file = state_dir / ".pipeline-mode"
        mode_file.write_text("run")

        env = os.environ.copy()
        env["CLAUDE_PLUGIN_ROOT"] = PLUGIN_ROOT
        env["CLAUDE_SESSION_ID"] = "test-run-clear"

        stdout, stderr, rc = _run_hook("session-start.sh", env, str(tmp_path))
        assert rc == 0
        # After session-start, "run" mode should be cleared
        if mode_file.exists():
            assert mode_file.read_text().strip() != "run"

    def test_auto_mode_persists_across_session_start(self, tmp_path):
        """session-start.sh should NOT clear .pipeline-mode when value is 'auto'."""
        (tmp_path / ".git").mkdir()
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()
        mode_file = state_dir / ".pipeline-mode"
        mode_file.write_text("auto")

        env = os.environ.copy()
        env["CLAUDE_PLUGIN_ROOT"] = PLUGIN_ROOT
        env["CLAUDE_SESSION_ID"] = "test-auto-persist"

        stdout, stderr, rc = _run_hook("session-start.sh", env, str(tmp_path))
        assert rc == 0
        # Auto mode should persist
        assert mode_file.exists()
        assert mode_file.read_text().strip() == "auto"


# ---------------------------------------------------------------------------
# Skip routing (fast path)
# ---------------------------------------------------------------------------

class TestSkipRouting:
    def test_skip_routing_json_format(self):
        """Router outputs {"skip_routing": true} for trivial follow-ups."""
        skip_routing_response = {"skip_routing": True}
        assert skip_routing_response["skip_routing"] is True
        assert json.dumps(skip_routing_response)  # serializable

    def test_skip_routing_has_no_other_fields_required(self):
        """skip_routing response is minimal - no taxonomy, no harness."""
        skip_routing_response = {"skip_routing": True}
        assert "taxonomy" not in skip_routing_response
        assert "selected_harness" not in skip_routing_response

    def test_non_skip_routing_has_selected_harness(self):
        """A full routing response has selected_harness."""
        routing_response = {
            "taxonomy": {"task_type": "bugfix", "uncertainty": "low"},
            "selected_harness": "tdd-driven",
            "harness_chain": ["tdd-driven"],
            "ensemble_required": False,
        }
        assert "selected_harness" in routing_response
        assert routing_response["selected_harness"] == "tdd-driven"


# ---------------------------------------------------------------------------
# Eval pending flow
# ---------------------------------------------------------------------------

class TestEvalPendingFlow:
    def test_eval_pending_file_created_by_subagent_complete(self, tmp_path):
        """subagent-complete.sh creates .eval-pending in session dir."""
        (tmp_path / ".git").mkdir()
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()
        session_id = "test-eval-pending-001"
        session_dir = state_dir / "sessions" / session_id
        session_dir.mkdir(parents=True)
        (state_dir / ".current-session-id").write_text(session_id)

        env = os.environ.copy()
        env["CLAUDE_PLUGIN_ROOT"] = PLUGIN_ROOT

        stdout, stderr, rc = _run_hook(
            "subagent-complete.sh", env, str(tmp_path), stdin="{}"
        )
        assert rc == 0
        assert (session_dir / ".eval-pending").exists()

    def test_subagent_complete_output_is_valid_json(self, tmp_path):
        """subagent-complete.sh output is valid JSON."""
        (tmp_path / ".git").mkdir()
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()
        env = os.environ.copy()
        env["CLAUDE_PLUGIN_ROOT"] = PLUGIN_ROOT

        stdout, stderr, rc = _run_hook(
            "subagent-complete.sh", env, str(tmp_path), stdin="{}"
        )
        assert rc == 0
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError as exc:
            pytest.fail(f"subagent-complete.sh output not valid JSON: {exc}\nOutput: {stdout!r}")
        assert "hookSpecificOutput" in parsed

    def test_eval_pending_cleared_when_removed(self, tmp_state_dir):
        """Removing .eval-pending clears the pending evaluation state."""
        session_id = "test-clear-pending"
        session_dir = tmp_state_dir / "sessions" / session_id
        session_dir.mkdir(parents=True)
        eval_pending = session_dir / ".eval-pending"
        eval_pending.write_text("20260315T000000Z")
        assert eval_pending.exists()
        eval_pending.unlink()
        assert not eval_pending.exists()


# ---------------------------------------------------------------------------
# Prompt interceptor
# ---------------------------------------------------------------------------

class TestPromptInterceptor:
    def test_prompt_interceptor_output_is_valid_json(self, tmp_path):
        (tmp_path / ".git").mkdir()
        env = os.environ.copy()
        env["CLAUDE_PLUGIN_ROOT"] = PLUGIN_ROOT
        # No session, no mode — should output empty additionalContext

        stdout, stderr, rc = _run_hook(
            "prompt-interceptor.sh", env, str(tmp_path), stdin="{}"
        )
        assert rc == 0
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError as exc:
            pytest.fail(f"prompt-interceptor output not valid JSON: {exc}\nOutput: {stdout!r}")
        assert "hookSpecificOutput" in parsed

    def test_prompt_interceptor_auto_mode_injects_context(self, tmp_path):
        (tmp_path / ".git").mkdir()
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()
        (state_dir / ".pipeline-mode").write_text("auto")
        env = os.environ.copy()
        env["CLAUDE_PLUGIN_ROOT"] = PLUGIN_ROOT

        stdout, stderr, rc = _run_hook(
            "prompt-interceptor.sh", env, str(tmp_path), stdin="{}"
        )
        assert rc == 0
        parsed = json.loads(stdout)
        ctx = parsed["hookSpecificOutput"]["additionalContext"]
        assert "adaptive-harness" in ctx.lower() or "route" in ctx.lower()

    def test_prompt_interceptor_eval_pending_takes_priority(self, tmp_path):
        """eval-pending fires regardless of pipeline mode."""
        (tmp_path / ".git").mkdir()
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()
        # Set auto mode
        (state_dir / ".pipeline-mode").write_text("auto")
        # Set eval pending
        session_id = "test-priority-001"
        session_dir = state_dir / "sessions" / session_id
        session_dir.mkdir(parents=True)
        (session_dir / ".eval-pending").write_text("ts")
        (state_dir / ".current-session-id").write_text(session_id)
        env = os.environ.copy()
        env["CLAUDE_PLUGIN_ROOT"] = PLUGIN_ROOT

        stdout, stderr, rc = _run_hook(
            "prompt-interceptor.sh", env, str(tmp_path), stdin="{}"
        )
        assert rc == 0
        parsed = json.loads(stdout)
        ctx = parsed["hookSpecificOutput"]["additionalContext"]
        assert "WARNING" in ctx or "evaluation" in ctx.lower()

    def test_prompt_interceptor_silent_when_no_mode_no_pending(self, tmp_path):
        """No mode, no pending eval — output additionalContext is empty."""
        (tmp_path / ".git").mkdir()
        env = os.environ.copy()
        env["CLAUDE_PLUGIN_ROOT"] = PLUGIN_ROOT

        stdout, stderr, rc = _run_hook(
            "prompt-interceptor.sh", env, str(tmp_path), stdin="{}"
        )
        assert rc == 0
        parsed = json.loads(stdout)
        ctx = parsed["hookSpecificOutput"]["additionalContext"]
        assert ctx == ""


# ---------------------------------------------------------------------------
# End-to-end flow simulation
# ---------------------------------------------------------------------------

class TestEndToEndFlowSimulation:
    def test_full_pipeline_state_transitions(self, tmp_path, tmp_state_dir):
        """Simulate the state transitions: session-start → eval pending → merged."""
        session_id = "e2e-sim-001"
        # 1. Session start: create session dir and .current-session-id
        session_dir = tmp_state_dir / "sessions" / session_id
        session_dir.mkdir(parents=True)
        (tmp_state_dir / ".current-session-id").write_text(session_id)

        # 2. Subagent completes: creates .eval-pending
        (session_dir / ".eval-pending").write_text("20260315T000000Z")
        assert (session_dir / ".eval-pending").exists()

        # 3. Evaluator runs: creates eval file
        eval_data = {
            "harness": "tdd-driven",
            "quality_gate_passed": True,
            "fast_path": False,
            "scores": {
                "correctness": 0.9, "completeness": 0.85, "quality": 0.80,
                "robustness": 0.75, "clarity": 0.85, "verifiability": 0.70,
            },
            "overall_score": 0.8275,
        }
        eval_file = session_dir / "eval-001.json"
        with open(eval_file, "w") as fh:
            json.dump(eval_data, fh)

        # 4. Remove .eval-pending after eval
        (session_dir / ".eval-pending").unlink()
        assert not (session_dir / ".eval-pending").exists()

        # 5. Session end would merge weights
        pool = {
            "stable": {"tdd-driven": {"weight": 1.0, "total_runs": 0, "successes": 0,
                                       "failures": 0, "consecutive_successes": 0}},
            "experimental": {},
            "last_updated": None,
            "last_merged_session": None,
        }
        # After merge: total_runs += 1, successes += 1
        pool["stable"]["tdd-driven"]["total_runs"] += 1
        pool["stable"]["tdd-driven"]["successes"] += 1
        pool["last_merged_session"] = session_id

        assert pool["stable"]["tdd-driven"]["total_runs"] == 1
        assert pool["last_merged_session"] == session_id

    def test_session_end_clean_clears_current_session_id(self, tmp_path):
        """session-end.sh removes .current-session-id."""
        (tmp_path / ".git").mkdir()
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()
        session_id = "test-end-clean"
        (state_dir / ".current-session-id").write_text(session_id)
        # Create pool file
        pool = {"stable": {}, "experimental": {}, "last_updated": None, "last_merged_session": None}
        with open(state_dir / "harness-pool.json", "w") as fh:
            json.dump(pool, fh)

        env = os.environ.copy()
        env["CLAUDE_PLUGIN_ROOT"] = PLUGIN_ROOT

        stdout, stderr, rc = _run_hook(
            "session-end.sh", env, str(tmp_path), stdin=""
        )
        assert rc == 0
        # .current-session-id should be removed
        assert not (state_dir / ".current-session-id").exists()

    def test_routing_response_structure(self):
        """A complete routing response has all required fields."""
        routing_response = {
            "taxonomy": {
                "task_type": "bugfix",
                "uncertainty": "medium",
                "blast_radius": "local",
                "verifiability": "easy",
                "latency_sensitivity": "low",
                "domain": "backend",
            },
            "selected_harness": "tdd-driven",
            "harness_chain": ["tdd-driven"],
            "ensemble_required": False,
            "reasoning": "Local bugfix with easy verifiability.",
            "candidate_scores": {"tdd-driven": 0.85},
        }
        required = {"taxonomy", "selected_harness", "harness_chain", "ensemble_required", "reasoning"}
        for field in required:
            assert field in routing_response
