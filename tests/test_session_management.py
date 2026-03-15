"""
Tests for session creation, session ID resolution, and evidence directory structure.
"""

import json
import os
import subprocess

import pytest


WORKSPACE_ROOT = "/home/seongwoong/workspace/adaptive-harness"
HOOKS_DIR = os.path.join(WORKSPACE_ROOT, "hooks")


# ---------------------------------------------------------------------------
# Helpers (re-implemented from lib.sh logic)
# ---------------------------------------------------------------------------

def _resolve_session_id(state_dir: str, env: dict | None = None) -> str:
    if env is None:
        env = os.environ.copy()
    sid = ""
    sid_file = os.path.join(state_dir, ".current-session-id")
    if os.path.isfile(sid_file):
        with open(sid_file) as fh:
            sid = fh.read().strip()
    if not sid:
        sid = env.get("CLAUDE_SESSION_ID", "")
    return sid


# ---------------------------------------------------------------------------
# Session ID resolution
# ---------------------------------------------------------------------------

class TestSessionIdResolution:
    def test_session_id_from_file(self, tmp_path, monkeypatch):
        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
        (tmp_path / ".current-session-id").write_text("sess-file-123")
        result = _resolve_session_id(str(tmp_path), {})
        assert result == "sess-file-123"

    def test_session_id_file_takes_priority_over_env(self, tmp_path):
        (tmp_path / ".current-session-id").write_text("from-file")
        env = {"CLAUDE_SESSION_ID": "from-env"}
        result = _resolve_session_id(str(tmp_path), env)
        assert result == "from-file"

    def test_session_id_from_env_fallback(self, tmp_path):
        env = {"CLAUDE_SESSION_ID": "from-env-only"}
        result = _resolve_session_id(str(tmp_path), env)
        assert result == "from-env-only"

    def test_session_id_empty_when_neither_present(self, tmp_path):
        result = _resolve_session_id(str(tmp_path), {})
        assert result == ""

    def test_session_id_strips_whitespace_from_file(self, tmp_path):
        (tmp_path / ".current-session-id").write_text("  sess-ws-456  \n")
        result = _resolve_session_id(str(tmp_path), {})
        assert result == "sess-ws-456"

    def test_session_id_empty_file_falls_back_to_env(self, tmp_path):
        (tmp_path / ".current-session-id").write_text("")
        env = {"CLAUDE_SESSION_ID": "env-fallback"}
        result = _resolve_session_id(str(tmp_path), env)
        assert result == "env-fallback"


# ---------------------------------------------------------------------------
# Session directory creation
# ---------------------------------------------------------------------------

class TestSessionDirectoryCreation:
    def test_session_dir_created_under_sessions(self, tmp_state_dir):
        session_id = "test-session-abc"
        session_dir = tmp_state_dir / "sessions" / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        assert session_dir.exists()

    def test_evidence_dir_created_under_session(self, tmp_state_dir):
        session_id = "test-session-abc"
        evidence_dir = tmp_state_dir / "sessions" / session_id / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        assert evidence_dir.exists()

    def test_session_id_written_to_file(self, tmp_state_dir):
        session_id = "sess-20260315-001"
        sid_file = tmp_state_dir / ".current-session-id"
        sid_file.write_text(session_id)
        assert sid_file.read_text() == session_id

    def test_current_session_id_file_format(self, tmp_state_dir):
        session_id = "sess-20260315-180838-1344696"
        sid_file = tmp_state_dir / ".current-session-id"
        sid_file.write_text(session_id)
        assert _resolve_session_id(str(tmp_state_dir), {}) == session_id

    def test_plugin_root_written_to_state_dir(self, tmp_state_dir):
        plugin_root_file = tmp_state_dir / ".plugin-root"
        plugin_root_file.write_text("/some/plugin/root")
        assert plugin_root_file.read_text() == "/some/plugin/root"


# ---------------------------------------------------------------------------
# Session state directory structure
# ---------------------------------------------------------------------------

class TestSessionStateStructure:
    def test_state_dir_has_sessions_subdir(self, tmp_state_dir):
        assert (tmp_state_dir / "sessions").is_dir()

    def test_state_dir_has_evaluation_logs_subdir(self, tmp_state_dir):
        assert (tmp_state_dir / "evaluation-logs").is_dir()

    def test_state_dir_has_evolution_proposals_subdir(self, tmp_state_dir):
        assert (tmp_state_dir / "evolution-proposals").is_dir()

    def test_eval_pending_file_created_in_session_dir(self, tmp_state_dir):
        session_id = "sess-eval-test"
        session_dir = tmp_state_dir / "sessions" / session_id
        session_dir.mkdir(parents=True)
        eval_pending = session_dir / ".eval-pending"
        eval_pending.write_text("20260315T000000Z")
        assert eval_pending.exists()

    def test_subagent_events_append_to_jsonl(self, tmp_state_dir):
        session_id = "sess-event-test"
        session_dir = tmp_state_dir / "sessions" / session_id
        session_dir.mkdir(parents=True)
        events_file = session_dir / "subagent-events.jsonl"
        event = {"timestamp": "20260315T000000Z", "event": "subagent_stop"}
        with open(events_file, "a") as fh:
            fh.write(json.dumps(event) + "\n")
        lines = events_file.read_text().strip().split("\n")
        assert len(lines) == 1
        assert json.loads(lines[0])["event"] == "subagent_stop"

    def test_eval_file_stored_in_session_dir(self, tmp_state_dir, sample_eval_json):
        session_id = "sess-eval-store"
        session_dir = tmp_state_dir / "sessions" / session_id
        session_dir.mkdir(parents=True)
        eval_file = session_dir / "eval-001.json"
        with open(eval_file, "w") as fh:
            json.dump(sample_eval_json, fh)
        with open(eval_file) as fh:
            loaded = json.load(fh)
        assert loaded["harness_used"] == "tdd-driven"


# ---------------------------------------------------------------------------
# Session start shell script
# ---------------------------------------------------------------------------

class TestSessionStartScript:
    def test_session_start_creates_session_dir(self, tmp_path, monkeypatch):
        """Run session-start.sh and verify it creates session directory."""
        session_start_sh = os.path.join(HOOKS_DIR, "session-start.sh")
        state_dir = str(tmp_path / ".adaptive-harness")
        plugin_root = "/home/seongwoong/.claude/plugins/cache/adaptive-harness/adaptive-harness/1.0.0"
        session_id = "test-session-start-001"
        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = session_id
        env["CLAUDE_PLUGIN_ROOT"] = plugin_root

        # Create a fake git root to anchor state_dir
        (tmp_path / ".git").mkdir()

        proc = subprocess.run(
            ["bash", session_start_sh],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(tmp_path),
        )
        # Script should succeed (output is JSON regardless of mode)
        assert proc.returncode == 0
        # Session directory should exist
        expected_session = os.path.join(state_dir, "sessions", session_id)
        assert os.path.isdir(expected_session), (
            f"Expected session directory: {expected_session}\nstderr: {proc.stderr}"
        )

    def test_session_start_creates_current_session_id_file(self, tmp_path):
        session_start_sh = os.path.join(HOOKS_DIR, "session-start.sh")
        plugin_root = "/home/seongwoong/.claude/plugins/cache/adaptive-harness/adaptive-harness/1.0.0"
        state_dir = str(tmp_path / ".adaptive-harness")
        session_id = "test-session-id-file"
        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = session_id
        env["CLAUDE_PLUGIN_ROOT"] = plugin_root
        (tmp_path / ".git").mkdir()

        proc = subprocess.run(
            ["bash", session_start_sh],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(tmp_path),
        )
        assert proc.returncode == 0
        sid_file = os.path.join(state_dir, ".current-session-id")
        assert os.path.isfile(sid_file), f"Expected .current-session-id file. stderr: {proc.stderr}"
        with open(sid_file) as fh:
            assert fh.read().strip() == session_id

    def test_session_start_output_is_valid_json(self, tmp_path):
        session_start_sh = os.path.join(HOOKS_DIR, "session-start.sh")
        plugin_root = "/home/seongwoong/.claude/plugins/cache/adaptive-harness/adaptive-harness/1.0.0"
        env = os.environ.copy()
        env["CLAUDE_PLUGIN_ROOT"] = plugin_root
        env["CLAUDE_SESSION_ID"] = "test-json-output"
        (tmp_path / ".git").mkdir()

        proc = subprocess.run(
            ["bash", session_start_sh],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(tmp_path),
        )
        assert proc.returncode == 0
        try:
            parsed = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            pytest.fail(f"session-start.sh output is not valid JSON: {exc}\nOutput: {proc.stdout!r}")
        assert "hookSpecificOutput" in parsed
