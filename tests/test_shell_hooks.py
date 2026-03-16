"""
Shell hook tests via subprocess.

Tests session-start.sh, session-end.sh, prompt-interceptor.sh,
and subagent-complete.sh.

Marked with @pytest.mark.shell for optional selective exclusion.
"""

import json
import os
import subprocess

import pytest


WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS_DIR = os.path.join(WORKSPACE_ROOT, "hooks")
PLUGIN_ROOT = WORKSPACE_ROOT

pytestmark = pytest.mark.shell


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


def _base_env(plugin_root: str = PLUGIN_ROOT, session_id: str = "test-shell-hooks-001") -> dict:
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = plugin_root
    env["CLAUDE_SESSION_ID"] = session_id
    return env


def _make_git_root(tmp_path):
    (tmp_path / ".git").mkdir(exist_ok=True)
    return tmp_path


# ---------------------------------------------------------------------------
# session-start.sh
# ---------------------------------------------------------------------------

class TestSessionStartHook:
    def test_exits_with_code_0(self, tmp_path):
        _make_git_root(tmp_path)
        env = _base_env()
        _, _, rc = _run_hook("session-start.sh", env, str(tmp_path))
        assert rc == 0

    def test_output_is_valid_json(self, tmp_path):
        _make_git_root(tmp_path)
        env = _base_env()
        stdout, _, rc = _run_hook("session-start.sh", env, str(tmp_path))
        assert rc == 0
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError as exc:
            pytest.fail(f"session-start.sh output is not valid JSON: {exc}\nOutput: {stdout!r}")
        assert "hookSpecificOutput" in parsed

    def test_creates_session_directory(self, tmp_path):
        _make_git_root(tmp_path)
        session_id = "session-start-test-dir"
        env = _base_env(session_id=session_id)
        stdout, stderr, rc = _run_hook("session-start.sh", env, str(tmp_path))
        assert rc == 0
        state_dir = tmp_path / ".adaptive-harness"
        expected = state_dir / "sessions" / session_id
        assert expected.is_dir(), f"Session dir missing. stderr: {stderr}"

    def test_creates_evidence_subdirectory(self, tmp_path):
        _make_git_root(tmp_path)
        session_id = "session-start-evidence"
        env = _base_env(session_id=session_id)
        _, _, rc = _run_hook("session-start.sh", env, str(tmp_path))
        assert rc == 0
        evidence_dir = tmp_path / ".adaptive-harness" / "sessions" / session_id / "evidence"
        assert evidence_dir.is_dir()

    def test_writes_current_session_id_file(self, tmp_path):
        _make_git_root(tmp_path)
        session_id = "session-start-sid-file"
        env = _base_env(session_id=session_id)
        _, _, rc = _run_hook("session-start.sh", env, str(tmp_path))
        assert rc == 0
        sid_file = tmp_path / ".adaptive-harness" / ".current-session-id"
        assert sid_file.exists()
        assert sid_file.read_text().strip() == session_id

    def test_bootstraps_harness_pool_when_absent(self, tmp_path):
        _make_git_root(tmp_path)
        env = _base_env()
        _, _, rc = _run_hook("session-start.sh", env, str(tmp_path))
        assert rc == 0
        pool_file = tmp_path / ".adaptive-harness" / "harness-pool.json"
        assert pool_file.exists()
        with open(pool_file) as fh:
            pool = json.load(fh)
        assert "stable" in pool
        assert len(pool["stable"]) > 0

    def test_creates_evaluation_logs_directory(self, tmp_path):
        _make_git_root(tmp_path)
        env = _base_env()
        _, _, rc = _run_hook("session-start.sh", env, str(tmp_path))
        assert rc == 0
        assert (tmp_path / ".adaptive-harness" / "evaluation-logs").is_dir()

    def test_creates_evolution_proposals_directory(self, tmp_path):
        _make_git_root(tmp_path)
        env = _base_env()
        _, _, rc = _run_hook("session-start.sh", env, str(tmp_path))
        assert rc == 0
        assert (tmp_path / ".adaptive-harness" / "evolution-proposals").is_dir()

    def test_auto_mode_injects_skill_content(self, tmp_path):
        _make_git_root(tmp_path)
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir(exist_ok=True)
        (state_dir / ".pipeline-mode").write_text("auto")
        env = _base_env()
        stdout, stderr, rc = _run_hook("session-start.sh", env, str(tmp_path))
        assert rc == 0
        parsed = json.loads(stdout)
        ctx = parsed["hookSpecificOutput"]["additionalContext"]
        # In auto mode, context should contain skill content (not empty)
        assert len(ctx) > 50 or "adaptive-harness" in ctx.lower()

    def test_no_mode_outputs_lightweight_message(self, tmp_path):
        _make_git_root(tmp_path)
        env = _base_env()
        stdout, _, rc = _run_hook("session-start.sh", env, str(tmp_path))
        assert rc == 0
        parsed = json.loads(stdout)
        ctx = parsed["hookSpecificOutput"]["additionalContext"]
        assert "adaptive-harness" in ctx.lower()


# ---------------------------------------------------------------------------
# session-end.sh
# ---------------------------------------------------------------------------

class TestSessionEndHook:
    def _create_state(self, tmp_path, session_id: str, pool: dict) -> str:
        _make_git_root(tmp_path)
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir(exist_ok=True)
        (state_dir / ".current-session-id").write_text(session_id)
        with open(state_dir / "harness-pool.json", "w") as fh:
            json.dump(pool, fh)
        return str(state_dir)

    def test_exits_with_code_0(self, tmp_path):
        pool = {"stable": {}, "experimental": {}, "last_updated": None, "last_merged_session": None}
        self._create_state(tmp_path, "end-test-001", pool)
        env = _base_env()
        _, _, rc = _run_hook("session-end.sh", env, str(tmp_path))
        assert rc == 0

    def test_removes_current_session_id_file(self, tmp_path):
        pool = {"stable": {}, "experimental": {}, "last_updated": None, "last_merged_session": None}
        self._create_state(tmp_path, "end-sid-test", pool)
        env = _base_env(session_id="end-sid-test")
        _, _, rc = _run_hook("session-end.sh", env, str(tmp_path))
        assert rc == 0
        assert not (tmp_path / ".adaptive-harness" / ".current-session-id").exists()

    def test_merges_eval_files_into_pool(self, tmp_path):
        pool = {
            "stable": {"tdd-driven": {"weight": 1.0, "total_runs": 0, "successes": 0,
                                       "failures": 0, "consecutive_successes": 0}},
            "experimental": {},
            "last_updated": None,
            "last_merged_session": None,
        }
        session_id = "end-merge-test"
        state_dir_str = self._create_state(tmp_path, session_id, pool)
        state_dir = tmp_path / ".adaptive-harness"
        session_dir = state_dir / "sessions" / session_id
        session_dir.mkdir(parents=True)
        eval_data = {"harness": "tdd-driven", "quality_gate_passed": True, "fast_path": False}
        with open(session_dir / "eval-001.json", "w") as fh:
            json.dump(eval_data, fh)

        env = _base_env(session_id=session_id)
        _, _, rc = _run_hook("session-end.sh", env, str(tmp_path))
        assert rc == 0

        with open(state_dir / "harness-pool.json") as fh:
            updated_pool = json.load(fh)
        assert updated_pool["stable"]["tdd-driven"]["total_runs"] == 1
        assert updated_pool["stable"]["tdd-driven"]["successes"] == 1

    def test_does_not_update_last_merged_with_unknown_session(self, tmp_path):
        pool = {
            "stable": {},
            "experimental": {},
            "last_updated": None,
            "last_merged_session": "previous-good-session",
        }
        self._create_state(tmp_path, "unknown", pool)
        env = _base_env(session_id="unknown")
        _, _, rc = _run_hook("session-end.sh", env, str(tmp_path))
        assert rc == 0

        state_dir = tmp_path / ".adaptive-harness"
        with open(state_dir / "harness-pool.json") as fh:
            updated_pool = json.load(fh)
        assert updated_pool["last_merged_session"] == "previous-good-session"

    def test_clears_run_mode_at_session_end(self, tmp_path):
        pool = {"stable": {}, "experimental": {}, "last_updated": None, "last_merged_session": None}
        self._create_state(tmp_path, "end-mode-test", pool)
        state_dir = tmp_path / ".adaptive-harness"
        (state_dir / ".pipeline-mode").write_text("run")

        env = _base_env(session_id="end-mode-test")
        _, _, rc = _run_hook("session-end.sh", env, str(tmp_path))
        assert rc == 0

        mode_file = state_dir / ".pipeline-mode"
        if mode_file.exists():
            assert mode_file.read_text().strip() != "run"


# ---------------------------------------------------------------------------
# prompt-interceptor.sh
# ---------------------------------------------------------------------------

class TestPromptInterceptorHook:
    def test_exits_with_code_0(self, tmp_path):
        _make_git_root(tmp_path)
        env = _base_env()
        _, _, rc = _run_hook("prompt-interceptor.sh", env, str(tmp_path))
        assert rc == 0

    def test_output_is_valid_json(self, tmp_path):
        _make_git_root(tmp_path)
        env = _base_env()
        stdout, _, rc = _run_hook("prompt-interceptor.sh", env, str(tmp_path))
        assert rc == 0
        parsed = json.loads(stdout)
        assert "hookSpecificOutput" in parsed

    def test_context_empty_when_no_mode_no_pending(self, tmp_path):
        _make_git_root(tmp_path)
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_SESSION_ID"}
        env["CLAUDE_PLUGIN_ROOT"] = PLUGIN_ROOT
        stdout, _, rc = _run_hook("prompt-interceptor.sh", env, str(tmp_path))
        assert rc == 0
        parsed = json.loads(stdout)
        assert parsed["hookSpecificOutput"]["additionalContext"] == ""

    def test_context_nonempty_in_auto_mode(self, tmp_path):
        _make_git_root(tmp_path)
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()
        (state_dir / ".pipeline-mode").write_text("auto")
        env = _base_env()
        stdout, _, rc = _run_hook("prompt-interceptor.sh", env, str(tmp_path))
        assert rc == 0
        parsed = json.loads(stdout)
        ctx = parsed["hookSpecificOutput"]["additionalContext"]
        assert len(ctx) > 0

    def test_eval_pending_overrides_auto_mode(self, tmp_path):
        _make_git_root(tmp_path)
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()
        (state_dir / ".pipeline-mode").write_text("auto")
        session_id = "interceptor-eval-test"
        session_dir = state_dir / "sessions" / session_id
        session_dir.mkdir(parents=True)
        (session_dir / ".eval-pending").write_text("ts")
        (state_dir / ".current-session-id").write_text(session_id)
        env = _base_env(session_id=session_id)
        stdout, _, rc = _run_hook("prompt-interceptor.sh", env, str(tmp_path))
        assert rc == 0
        parsed = json.loads(stdout)
        ctx = parsed["hookSpecificOutput"]["additionalContext"]
        assert "WARNING" in ctx

    def test_chain_in_progress_overrides_auto_mode(self, tmp_path):
        """When .chain-in-progress exists, prompt-interceptor should inject chain continuation,
        not auto-mode routing or eval-pending warning."""
        _make_git_root(tmp_path)
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()
        (state_dir / ".pipeline-mode").write_text("auto")
        (state_dir / ".chain-in-progress").write_text("chain-data")
        env = _base_env()
        stdout, _, rc = _run_hook("prompt-interceptor.sh", env, str(tmp_path))
        assert rc == 0
        parsed = json.loads(stdout)
        ctx = parsed["hookSpecificOutput"]["additionalContext"]
        assert "CHAIN IN PROGRESS" in ctx
        assert "router" not in ctx.lower() or "Do NOT spawn the router" in ctx

    def test_chain_in_progress_overrides_eval_pending(self, tmp_path):
        """Chain in progress takes priority over eval-pending."""
        _make_git_root(tmp_path)
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()
        (state_dir / ".pipeline-mode").write_text("auto")
        (state_dir / ".chain-in-progress").write_text("chain-data")
        session_id = "chain-eval-test"
        session_dir = state_dir / "sessions" / session_id
        session_dir.mkdir(parents=True)
        (session_dir / ".eval-pending").write_text("ts")
        (state_dir / ".current-session-id").write_text(session_id)
        env = _base_env(session_id=session_id)
        stdout, _, rc = _run_hook("prompt-interceptor.sh", env, str(tmp_path))
        assert rc == 0
        parsed = json.loads(stdout)
        ctx = parsed["hookSpecificOutput"]["additionalContext"]
        # Chain should take priority over eval-pending
        assert "CHAIN IN PROGRESS" in ctx
        assert "WARNING" not in ctx


# ---------------------------------------------------------------------------
# subagent-complete.sh
# ---------------------------------------------------------------------------

class TestSubagentCompleteHook:
    def test_exits_with_code_0(self, tmp_path):
        _make_git_root(tmp_path)
        env = _base_env()
        _, _, rc = _run_hook("subagent-complete.sh", env, str(tmp_path), stdin="{}")
        assert rc == 0

    def test_output_is_valid_json(self, tmp_path):
        _make_git_root(tmp_path)
        env = _base_env()
        stdout, _, rc = _run_hook("subagent-complete.sh", env, str(tmp_path), stdin="{}")
        assert rc == 0
        parsed = json.loads(stdout)
        assert "hookSpecificOutput" in parsed

    def test_output_mentions_evaluation_pending(self, tmp_path):
        _make_git_root(tmp_path)
        env = _base_env()
        stdout, _, rc = _run_hook("subagent-complete.sh", env, str(tmp_path), stdin="{}")
        assert rc == 0
        parsed = json.loads(stdout)
        ctx = parsed["hookSpecificOutput"]["additionalContext"]
        assert "EVALUATION PENDING" in ctx or "evaluation" in ctx.lower()

    def test_creates_eval_pending_in_session_dir(self, tmp_path):
        _make_git_root(tmp_path)
        session_id = "subagent-test-001"
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()
        session_dir = state_dir / "sessions" / session_id
        session_dir.mkdir(parents=True)
        (state_dir / ".current-session-id").write_text(session_id)

        env = _base_env(session_id=session_id)
        _, _, rc = _run_hook("subagent-complete.sh", env, str(tmp_path), stdin="{}")
        assert rc == 0
        assert (session_dir / ".eval-pending").exists()

    def test_appends_subagent_event_to_jsonl(self, tmp_path):
        _make_git_root(tmp_path)
        session_id = "subagent-events-test"
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()
        session_dir = state_dir / "sessions" / session_id
        session_dir.mkdir(parents=True)
        (state_dir / ".current-session-id").write_text(session_id)

        env = _base_env(session_id=session_id)
        _, _, rc = _run_hook("subagent-complete.sh", env, str(tmp_path), stdin="{}")
        assert rc == 0

        events_file = session_dir / "subagent-events.jsonl"
        assert events_file.exists()
        lines = events_file.read_text().strip().split("\n")
        assert len(lines) >= 1
        event = json.loads(lines[0])
        assert event["event"] == "subagent_stop"

    def test_chain_in_progress_skips_eval_pending(self, tmp_path):
        """When .chain-in-progress exists, subagent-complete should NOT write .eval-pending."""
        _make_git_root(tmp_path)
        session_id = "chain-test-001"
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()
        session_dir = state_dir / "sessions" / session_id
        session_dir.mkdir(parents=True)
        (state_dir / ".current-session-id").write_text(session_id)
        # Mark chain as in progress
        (state_dir / ".chain-in-progress").write_text("ralplan-consensus,careful-refactor")

        env = _base_env(session_id=session_id)
        stdout, _, rc = _run_hook("subagent-complete.sh", env, str(tmp_path), stdin="{}")
        assert rc == 0
        # .eval-pending should NOT be created during chain
        assert not (session_dir / ".eval-pending").exists()
        # Output should mention chain continuation, not evaluation
        parsed = json.loads(stdout)
        ctx = parsed["hookSpecificOutput"]["additionalContext"]
        assert "Chain step completed" in ctx
        assert "EVALUATION PENDING" not in ctx

    def test_no_chain_marker_creates_eval_pending(self, tmp_path):
        """Without .chain-in-progress, subagent-complete creates .eval-pending as before."""
        _make_git_root(tmp_path)
        session_id = "no-chain-test-001"
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()
        session_dir = state_dir / "sessions" / session_id
        session_dir.mkdir(parents=True)
        (state_dir / ".current-session-id").write_text(session_id)

        env = _base_env(session_id=session_id)
        stdout, _, rc = _run_hook("subagent-complete.sh", env, str(tmp_path), stdin="{}")
        assert rc == 0
        assert (session_dir / ".eval-pending").exists()
        parsed = json.loads(stdout)
        ctx = parsed["hookSpecificOutput"]["additionalContext"]
        assert "EVALUATION PENDING" in ctx
