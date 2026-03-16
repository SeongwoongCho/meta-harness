"""
Regression tests that directly test the shell scripts via subprocess.
These tests FAIL against the old buggy working tree and PASS after fixes.
"""

import json
import os
import shutil
import subprocess
import tempfile
import textwrap

import pytest


HOOKS_DIR = os.path.join(os.path.dirname(__file__), "..", "hooks")


def run_bash_function(script: str, func: str, args: list[str], env: dict | None = None) -> tuple[str, str, int]:
    """Source a bash script and call a function, returning (stdout, stderr, returncode)."""
    cmd = ["bash", "-c", f'source "{script}" && {func} {" ".join(args)}']
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return result.stdout.strip(), result.stderr.strip(), result.returncode


# ---------------------------------------------------------------------------
# Regression test for resolve_session_id (lib.sh)
# ---------------------------------------------------------------------------

class TestResolveSessionIdShell:
    """Tests that directly call the bash resolve_session_id function from lib.sh."""

    def test_shell_resolve_session_id_prefers_file_over_env(self, tmp_path, monkeypatch):
        """
        Shell resolve_session_id must prefer .current-session-id file over env var.
        Fails against old lib.sh (which checked env first).
        """
        lib_sh = os.path.join(HOOKS_DIR, "lib.sh")
        sid_file = tmp_path / ".current-session-id"
        sid_file.write_text("file-session-abc")

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = "env-session-xyz"

        stdout, stderr, rc = run_bash_function(lib_sh, "resolve_session_id", [str(tmp_path)], env)

        assert stdout == "file-session-abc", (
            f"Expected 'file-session-abc' (from file) but got '{stdout}'. "
            "This fails if lib.sh still checks CLAUDE_SESSION_ID before the file."
        )

    def test_shell_resolve_session_id_uses_env_when_file_missing(self, tmp_path, monkeypatch):
        """When .current-session-id is absent, CLAUDE_SESSION_ID must be returned."""
        lib_sh = os.path.join(HOOKS_DIR, "lib.sh")
        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = "env-only-session"

        stdout, stderr, rc = run_bash_function(lib_sh, "resolve_session_id", [str(tmp_path)], env)

        assert stdout == "env-only-session"

    def test_shell_resolve_session_id_empty_when_neither_present(self, tmp_path):
        """When neither source exists, output should be empty."""
        lib_sh = os.path.join(HOOKS_DIR, "lib.sh")
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_SESSION_ID"}

        stdout, stderr, rc = run_bash_function(lib_sh, "resolve_session_id", [str(tmp_path)], env)

        assert stdout == ""


# ---------------------------------------------------------------------------
# Regression test for session-end.sh merge logic
# ---------------------------------------------------------------------------

class TestSessionEndMergeShell:
    """Tests that run session-end.sh logic via Python (extracted heredoc)."""

    def _extract_and_run_merge_pyeof(self, pool: dict, weights: dict,
                                      session_dir: str, timestamp: str,
                                      session_id: str) -> dict:
        """
        Extracts the PYEOF heredoc from session-end.sh and runs it in a temp env.
        Returns the merged pool dict.
        """
        pool_file = os.path.join(session_dir, "pool.json")
        weights_file = os.path.join(session_dir, "weights.json")
        tmp_file = os.path.join(session_dir, "pool.json.tmp")

        with open(pool_file, "w") as fh:
            json.dump(pool, fh)
        if weights:
            with open(weights_file, "w") as fh:
                json.dump(weights, fh)

        # Extract the PYEOF block from the actual script
        session_end_sh = os.path.join(HOOKS_DIR, "session-end.sh")
        with open(session_end_sh) as fh:
            content = fh.read()

        start = content.find("<<'PYEOF'\n") + len("<<'PYEOF'\n")
        end = content.find("\nPYEOF", start)
        pyeof_code = content[start:end]

        # Run it
        env_args = [pool_file, weights_file, tmp_file, timestamp, session_id]
        proc = subprocess.run(
            ["python3", "-", *env_args],
            input=pyeof_code,
            capture_output=True,
            text=True,
        )

        assert proc.returncode == 0, f"PYEOF script failed: {proc.stderr}"

        with open(pool_file) as fh:
            return json.load(fh)

    def test_session_end_merge_does_not_write_unknown_session_id(self, tmp_path):
        """
        Fixed bug: session_id='unknown' must NOT overwrite last_merged_session.
        """
        pool = {
            "stable": {"h1": {"weight": 1.0, "total_runs": 0, "successes": 0, "failures": 0, "consecutive_successes": 0}},
            "experimental": {},
            "last_updated": None,
            "last_merged_session": "previous-good-session",
        }

        result = self._extract_and_run_merge_pyeof(
            pool, {}, str(tmp_path), "2026T000000Z", "unknown"
        )

        assert result["last_merged_session"] == "previous-good-session", (
            "last_merged_session must not be overwritten with 'unknown'. "
            "Old session-end.sh always wrote session_id unconditionally."
        )

    def test_session_end_merge_updates_counters_from_eval_files(self, tmp_path):
        """Eval files in session dir update harness counters in the pool."""
        pool = {
            "stable": {"h1": {"weight": 1.0, "total_runs": 0, "successes": 0, "failures": 0, "consecutive_successes": 0}},
            "experimental": {},
            "last_updated": None,
            "last_merged_session": None,
        }

        # Create eval files in the session dir (same directory as weights_file)
        eval_data = {"harness": "h1", "quality_gate_passed": True, "fast_path": False}
        eval_path = os.path.join(str(tmp_path), "eval-001.json")
        with open(eval_path, "w") as fh:
            json.dump(eval_data, fh)

        result = self._extract_and_run_merge_pyeof(
            pool, {}, str(tmp_path), "2026T000000Z", "sess-1"
        )

        assert result["stable"]["h1"]["total_runs"] == 1
        assert result["stable"]["h1"]["successes"] == 1
        assert result["last_merged_session"] == "sess-1"


# ---------------------------------------------------------------------------
# Regression test for session-start.sh proposal application
# (idempotency guard via subprocess Python extraction)
# ---------------------------------------------------------------------------

class TestSessionStartIdempotencyShell:
    """Tests that run the APPLY_PROPOSALS heredoc from session-start.sh."""

    def _extract_and_run_apply_proposals(self, proposals_dir: str, pool: dict,
                                          harnesses_dir: str,
                                          local_harnesses_dir: str | None = None) -> dict:
        """
        Extracts the APPLY_PROPOSALS block from session-start.sh and runs it.
        Returns the updated pool dict.
        """
        pool_file = os.path.join(proposals_dir, "..", "pool.json")
        pool_file = os.path.normpath(pool_file)

        with open(pool_file, "w") as fh:
            json.dump(pool, fh)

        if local_harnesses_dir is None:
            local_harnesses_dir = os.path.join(os.path.dirname(proposals_dir), "local-harnesses")
        os.makedirs(local_harnesses_dir, exist_ok=True)

        session_start_sh = os.path.join(HOOKS_DIR, "session-start.sh")
        with open(session_start_sh) as fh:
            content = fh.read()

        start = content.find("<<'APPLY_PROPOSALS'\n") + len("<<'APPLY_PROPOSALS'\n")
        end = content.find("\nAPPLY_PROPOSALS", start)
        apply_code = content[start:end]

        env_args = [proposals_dir, pool_file, harnesses_dir, local_harnesses_dir]
        proc = subprocess.run(
            ["python3", "-", *env_args],
            input=apply_code,
            capture_output=True,
            text=True,
        )

        assert proc.returncode == 0, f"APPLY_PROPOSALS script failed: {proc.stderr}"

        with open(pool_file) as fh:
            return json.load(fh)

    def test_apply_proposals_creates_experimental_dir(self, tmp_path):
        """A content_modification proposal must create an experimental harness dir."""
        harnesses_dir = str(tmp_path / "harnesses")
        proposals_dir = str(tmp_path / "proposals")
        local_harnesses_dir = str(tmp_path / "local-harnesses")
        os.makedirs(harnesses_dir)
        os.makedirs(proposals_dir)

        # Create a base harness
        base_dir = os.path.join(harnesses_dir, "base-harness")
        os.makedirs(base_dir)
        with open(os.path.join(base_dir, "skill.md"), "w") as fh:
            fh.write("# Base Skill\n")

        pool = {"stable": {}, "experimental": {}, "last_updated": None, "last_merged_session": None}
        proposal = {
            "status": "pending",
            "proposal_type": "content_modification",
            "harness": "base-harness",
            "experimental_harness_path": "harnesses/experimental/base-harness-v2",
            "proposed_change": {
                "file_path": "skill.md",
                "change_type": "add_section",
                "content": "## Added Section\nNew content here.",
                "location": "end",
            },
        }
        proposal_file = os.path.join(proposals_dir, "001-proposal.json")
        with open(proposal_file, "w") as fh:
            json.dump(proposal, fh)

        result_pool = self._extract_and_run_apply_proposals(proposals_dir, pool, harnesses_dir,
                                                             local_harnesses_dir)

        exp_dir = tmp_path / "local-harnesses" / "experimental" / "base-harness-v2"
        assert exp_dir.exists(), "Experimental harness directory must be created in local-harnesses"
        assert "base-harness-v2" in result_pool["experimental"]

    def test_apply_proposals_content_idempotent(self, tmp_path):
        """Running APPLY_PROPOSALS twice must not duplicate section content."""
        harnesses_dir = str(tmp_path / "harnesses")
        proposals_dir = str(tmp_path / "proposals")
        local_harnesses_dir = str(tmp_path / "local-harnesses")
        os.makedirs(harnesses_dir)
        os.makedirs(proposals_dir)

        base_dir = os.path.join(harnesses_dir, "base-harness")
        os.makedirs(base_dir)
        with open(os.path.join(base_dir, "skill.md"), "w") as fh:
            fh.write("# Base Skill\n")

        pool = {"stable": {}, "experimental": {}, "last_updated": None, "last_merged_session": None}
        proposal = {
            "status": "pending",
            "proposal_type": "content_modification",
            "harness": "base-harness",
            "experimental_harness_path": "harnesses/experimental/base-harness-v2",
            "proposed_change": {
                "file_path": "skill.md",
                "change_type": "add_section",
                "content": "## Idempotent Section\nMust appear only once.",
            },
        }
        proposal_file = os.path.join(proposals_dir, "001-proposal.json")
        with open(proposal_file, "w") as fh:
            json.dump(proposal, fh)

        # First run
        result_pool = self._extract_and_run_apply_proposals(proposals_dir, pool, harnesses_dir,
                                                             local_harnesses_dir)

        # Reset proposal status to simulate re-running on pending
        with open(proposal_file, "w") as fh:
            proposal["status"] = "pending"
            json.dump(proposal, fh)

        # Second run
        self._extract_and_run_apply_proposals(proposals_dir, result_pool, harnesses_dir,
                                               local_harnesses_dir)

        skill_content = (tmp_path / "local-harnesses" / "experimental" / "base-harness-v2" / "skill.md").read_text()
        count = skill_content.count("## Idempotent Section")
        assert count == 1, (
            f"Section appeared {count} times after 2 runs; expected 1. "
            "This fails if the idempotency guard is missing from session-start.sh."
        )
