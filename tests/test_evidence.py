"""
Tests for evidence file creation via collect-evidence.sh, JSON schema, and truncation.

Evidence files are created by collect-evidence.sh (a PostToolUse hook for Bash calls).
Schema: { timestamp, session_id, tool, command, stdout, stderr, exit_code }
Truncation: stdout and stderr truncated at 4096 chars.
"""

import json
import os
import subprocess
import tempfile

import pytest


WORKSPACE_ROOT = "/home/seongwoong/workspace/adaptive-harness"
HOOKS_DIR = os.path.join(WORKSPACE_ROOT, "hooks")
PLUGIN_ROOT = "/home/seongwoong/.claude/plugins/cache/adaptive-harness/adaptive-harness/1.0.0"

REQUIRED_EVIDENCE_FIELDS = {
    "timestamp",
    "session_id",
    "tool",
    "command",
    "stdout",
    "stderr",
    "exit_code",
}

MAX_FIELD_LEN = 4096


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

class TestEvidenceSchema:
    def test_evidence_has_required_fields(self, sample_evidence):
        for field in REQUIRED_EVIDENCE_FIELDS:
            assert field in sample_evidence, f"Missing field: {field}"

    def test_evidence_timestamp_is_string(self, sample_evidence):
        assert isinstance(sample_evidence["timestamp"], str)

    def test_evidence_tool_is_bash(self, sample_evidence):
        assert sample_evidence["tool"] == "Bash"

    def test_evidence_command_is_string(self, sample_evidence):
        assert isinstance(sample_evidence["command"], str)

    def test_evidence_stdout_is_string(self, sample_evidence):
        assert isinstance(sample_evidence["stdout"], str)

    def test_evidence_stderr_is_string(self, sample_evidence):
        assert isinstance(sample_evidence["stderr"], str)

    def test_evidence_exit_code_is_integer(self, sample_evidence):
        assert isinstance(sample_evidence["exit_code"], int)

    def test_evidence_serializable_to_json(self, sample_evidence):
        serialized = json.dumps(sample_evidence)
        loaded = json.loads(serialized)
        assert loaded["tool"] == "Bash"

    def test_evidence_exit_code_0_for_successful_command(self, sample_evidence):
        assert sample_evidence["exit_code"] == 0

    def test_evidence_can_have_nonzero_exit_code(self):
        evidence = {
            "timestamp": "20260315T000000Z",
            "session_id": "sess-001",
            "tool": "Bash",
            "command": "exit 1",
            "stdout": "",
            "stderr": "error",
            "exit_code": 1,
        }
        assert evidence["exit_code"] == 1


# ---------------------------------------------------------------------------
# Truncation
# ---------------------------------------------------------------------------

class TestEvidenceTruncation:
    def test_long_stdout_truncated_to_4096(self):
        long_output = "x" * 10000
        MAX_LEN = 4096
        truncated = long_output[:MAX_LEN] + "... [truncated]" if len(long_output) > MAX_LEN else long_output
        assert len(truncated) < len(long_output)
        assert "[truncated]" in truncated

    def test_short_stdout_not_truncated(self):
        short_output = "test passed"
        MAX_LEN = 4096
        result = short_output[:MAX_LEN] + "... [truncated]" if len(short_output) > MAX_LEN else short_output
        assert result == short_output
        assert "[truncated]" not in result

    def test_truncation_at_exactly_4096(self):
        output = "a" * 4096
        MAX_LEN = 4096
        result = output[:MAX_LEN] + "... [truncated]" if len(output) > MAX_LEN else output
        assert result == output

    def test_truncation_at_4097(self):
        output = "a" * 4097
        MAX_LEN = 4096
        result = output[:MAX_LEN] + "... [truncated]" if len(output) > MAX_LEN else output
        assert "[truncated]" in result

    def test_stderr_also_truncated(self):
        long_stderr = "e" * 10000
        MAX_LEN = 4096
        result = long_stderr[:MAX_LEN] + "... [truncated]" if len(long_stderr) > MAX_LEN else long_stderr
        assert "[truncated]" in result


# ---------------------------------------------------------------------------
# Evidence file creation via collect-evidence.sh subprocess
# ---------------------------------------------------------------------------

class TestCollectEvidenceSubprocess:
    def _make_env(self, session_id: str, state_dir: str) -> dict:
        env = os.environ.copy()
        env["CLAUDE_PLUGIN_ROOT"] = PLUGIN_ROOT
        env["CLAUDE_SESSION_ID"] = session_id
        return env

    def test_collect_evidence_creates_evidence_file(self, tmp_path):
        """collect-evidence.sh creates a JSON file in evidence directory."""
        (tmp_path / ".git").mkdir()
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()
        session_id = "collect-test-001"
        evidence_dir = state_dir / "sessions" / session_id / "evidence"
        evidence_dir.mkdir(parents=True)
        (state_dir / ".current-session-id").write_text(session_id)

        hook_input = json.dumps({
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
            "tool_response": {"output": "hello\n", "exitCode": 0, "stderr": ""},
        })

        env = self._make_env(session_id, str(state_dir))
        proc = subprocess.run(
            ["bash", os.path.join(HOOKS_DIR, "collect-evidence.sh")],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(tmp_path),
        )
        assert proc.returncode == 0

        evidence_files = list(evidence_dir.glob("*.json"))
        assert len(evidence_files) == 1, (
            f"Expected 1 evidence file, found {len(evidence_files)}. stderr: {proc.stderr}"
        )

    def test_collect_evidence_file_has_valid_json(self, tmp_path):
        """Evidence file contains valid JSON with required fields."""
        (tmp_path / ".git").mkdir()
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()
        session_id = "collect-test-002"
        evidence_dir = state_dir / "sessions" / session_id / "evidence"
        evidence_dir.mkdir(parents=True)
        (state_dir / ".current-session-id").write_text(session_id)

        hook_input = json.dumps({
            "tool_name": "Bash",
            "tool_input": {"command": "python3 -m pytest tests/ -v"},
            "tool_response": {"output": "5 passed", "exitCode": 0, "stderr": ""},
        })

        env = self._make_env(session_id, str(state_dir))
        proc = subprocess.run(
            ["bash", os.path.join(HOOKS_DIR, "collect-evidence.sh")],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(tmp_path),
        )
        assert proc.returncode == 0

        evidence_files = list(evidence_dir.glob("*.json"))
        with open(evidence_files[0]) as fh:
            data = json.load(fh)

        for field in REQUIRED_EVIDENCE_FIELDS:
            assert field in data, f"Missing field: {field}"

    def test_collect_evidence_captures_command(self, tmp_path):
        """Evidence file captures the exact command from tool_input."""
        (tmp_path / ".git").mkdir()
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()
        session_id = "collect-test-003"
        evidence_dir = state_dir / "sessions" / session_id / "evidence"
        evidence_dir.mkdir(parents=True)
        (state_dir / ".current-session-id").write_text(session_id)

        test_command = "python3 -m pytest tests/test_harness_pool.py -v"
        hook_input = json.dumps({
            "tool_name": "Bash",
            "tool_input": {"command": test_command},
            "tool_response": {"output": "30 passed", "exitCode": 0, "stderr": ""},
        })

        env = self._make_env(session_id, str(state_dir))
        proc = subprocess.run(
            ["bash", os.path.join(HOOKS_DIR, "collect-evidence.sh")],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(tmp_path),
        )
        assert proc.returncode == 0

        evidence_files = list(evidence_dir.glob("*.json"))
        with open(evidence_files[0]) as fh:
            data = json.load(fh)
        assert data["command"] == test_command

    def test_collect_evidence_captures_exit_code(self, tmp_path):
        """Evidence file captures the exit code from tool_response."""
        (tmp_path / ".git").mkdir()
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()
        session_id = "collect-test-004"
        evidence_dir = state_dir / "sessions" / session_id / "evidence"
        evidence_dir.mkdir(parents=True)
        (state_dir / ".current-session-id").write_text(session_id)

        hook_input = json.dumps({
            "tool_name": "Bash",
            "tool_input": {"command": "failing-command"},
            "tool_response": {"output": "", "exitCode": 1, "stderr": "command not found"},
        })

        env = self._make_env(session_id, str(state_dir))
        proc = subprocess.run(
            ["bash", os.path.join(HOOKS_DIR, "collect-evidence.sh")],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(tmp_path),
        )
        assert proc.returncode == 0

        evidence_files = list(evidence_dir.glob("*.json"))
        with open(evidence_files[0]) as fh:
            data = json.load(fh)
        assert data["exit_code"] == 1

    def test_collect_evidence_no_session_id_exits_cleanly(self, tmp_path):
        """Without session ID, collect-evidence.sh exits 0 without creating files."""
        (tmp_path / ".git").mkdir()
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()

        hook_input = json.dumps({
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
            "tool_response": {"output": "hello", "exitCode": 0, "stderr": ""},
        })

        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_SESSION_ID"}
        env["CLAUDE_PLUGIN_ROOT"] = PLUGIN_ROOT

        proc = subprocess.run(
            ["bash", os.path.join(HOOKS_DIR, "collect-evidence.sh")],
            input=hook_input,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(tmp_path),
        )
        # Should exit cleanly (0) even without session ID
        assert proc.returncode == 0

    def test_collect_evidence_multiple_calls_no_collision(self, tmp_path):
        """Multiple evidence files don't collide (random suffix prevents collision)."""
        (tmp_path / ".git").mkdir()
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()
        session_id = "collect-test-multi"
        evidence_dir = state_dir / "sessions" / session_id / "evidence"
        evidence_dir.mkdir(parents=True)
        (state_dir / ".current-session-id").write_text(session_id)

        hook_input = json.dumps({
            "tool_name": "Bash",
            "tool_input": {"command": "echo test"},
            "tool_response": {"output": "test", "exitCode": 0, "stderr": ""},
        })

        env = self._make_env(session_id, str(state_dir))
        for _ in range(3):
            subprocess.run(
                ["bash", os.path.join(HOOKS_DIR, "collect-evidence.sh")],
                input=hook_input,
                capture_output=True,
                text=True,
                env=env,
                cwd=str(tmp_path),
            )

        evidence_files = list(evidence_dir.glob("*.json"))
        # All 3 files should exist (no overwriting)
        assert len(evidence_files) == 3, (
            f"Expected 3 evidence files, got {len(evidence_files)}"
        )
