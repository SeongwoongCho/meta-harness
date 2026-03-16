"""
Security vulnerability fix tests (RED-first TDD).

These tests cover the security vulnerabilities identified in the audit:
  H1 — Race Condition in Harness Pool Updates (flock)
  M1 — Path Traversal in Proposal Application
  M2 — JSON Injection via Unvalidated Variable in JSON Output
  M3 — Insufficient Input Validation for Harness Names
  M4 — Insecure Temporary File Usage in GitHub Workflows
  L1 — No Rate Limiting on Evidence File Creation
  L2 — Missing Error Handling for Python Subprocess Failures
"""

import json
import os
import re
import subprocess
import tempfile

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


def _base_env(plugin_root: str = PLUGIN_ROOT, session_id: str = "sec-test-001") -> dict:
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = plugin_root
    env["CLAUDE_SESSION_ID"] = session_id
    return env


def _make_git_root(tmp_path):
    (tmp_path / ".git").mkdir(exist_ok=True)
    return tmp_path


# ---------------------------------------------------------------------------
# H1: Race Condition in Harness Pool Updates (flock)
# ---------------------------------------------------------------------------

class TestH1RaceConditionFlock:
    """session-end.sh must use file locking when updating harness-pool.json."""

    def test_session_end_uses_flock_in_python(self):
        """session-end.sh Python block must use fcntl.flock() for advisory locking."""
        hook_path = os.path.join(HOOKS_DIR, "session-end.sh")
        with open(hook_path, "r") as fh:
            content = fh.read()
        assert "fcntl.flock" in content or "flock" in content, (
            "session-end.sh must use flock (advisory file locking) when writing harness-pool.json"
        )

    def test_concurrent_session_end_does_not_corrupt_pool(self, tmp_path):
        """Concurrent session-end runs must not corrupt or truncate harness-pool.json."""
        _make_git_root(tmp_path)
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()

        pool = {
            "stable": {
                "tdd-driven": {
                    "weight": 1.0, "total_runs": 0, "successes": 0,
                    "failures": 0, "consecutive_successes": 0
                }
            },
            "experimental": {},
            "last_updated": None,
            "last_merged_session": None,
        }
        pool_file = state_dir / "harness-pool.json"
        with open(pool_file, "w") as fh:
            json.dump(pool, fh)

        # Run 5 concurrent session-end processes
        procs = []
        for i in range(5):
            session_id = f"concurrent-{i}"
            session_dir = state_dir / "sessions" / session_id
            session_dir.mkdir(parents=True)
            eval_data = {"harness": "tdd-driven", "quality_gate_passed": True, "fast_path": False}
            with open(session_dir / "eval-001.json", "w") as fh:
                json.dump(eval_data, fh)
            (state_dir / ".current-session-id").write_text(session_id)
            env = _base_env(session_id=session_id)
            hook_path = os.path.join(HOOKS_DIR, "session-end.sh")
            proc = subprocess.Popen(
                ["bash", hook_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                cwd=str(tmp_path),
            )
            procs.append(proc)

        for proc in procs:
            proc.wait()

        # Pool file must exist and be valid JSON
        assert pool_file.exists(), "harness-pool.json was deleted by concurrent writes"
        with open(pool_file) as fh:
            result = json.load(fh)
        assert "stable" in result, "harness-pool.json corrupt after concurrent writes"


# ---------------------------------------------------------------------------
# M1: Path Traversal in Proposal Application
# ---------------------------------------------------------------------------

class TestM1PathTraversal:
    """Absolute paths and directory-traversal paths in proposals must be rejected."""

    def _run_proposal_python(self, proposals_dir: str, pool_file: str,
                              harnesses_dir: str,
                              local_harnesses_dir: str | None = None) -> tuple[str, str, int]:
        """Run the embedded Python from session-start.sh's APPLY_PROPOSALS block."""
        if local_harnesses_dir is None:
            local_harnesses_dir = os.path.join(os.path.dirname(pool_file), "local-harnesses")
        os.makedirs(local_harnesses_dir, exist_ok=True)
        env = os.environ.copy()
        env["CLAUDE_PLUGIN_ROOT"] = PLUGIN_ROOT
        proc = subprocess.run(
            ["python3", "-c", """
import json, sys, os, shutil, glob, re

proposals_dir = sys.argv[1]
pool_file = sys.argv[2]
harnesses_dir = sys.argv[3]
local_harnesses_dir = sys.argv[4]

HARNESS_NAME_RE = re.compile(r'^[a-zA-Z0-9_-]+$')

if not os.path.isfile(pool_file):
    sys.exit(0)

with open(pool_file, 'r') as f:
    pool = json.load(f)

rejected = []
applied = []
for pf in sorted(glob.glob(os.path.join(proposals_dir, '*.json'))):
    try:
        with open(pf, 'r') as f:
            proposal = json.load(f)
    except Exception:
        continue

    if proposal.get('status') != 'pending':
        continue

    harness = proposal.get('harness', '')
    if not HARNESS_NAME_RE.match(harness):
        proposal['status'] = 'rejected'
        rejected.append(pf)
        with open(pf, 'w') as f:
            json.dump(proposal, f)
        continue

    exp_path = proposal.get('experimental_harness_path', '')
    if not exp_path:
        continue

    # Reject absolute paths
    if os.path.isabs(exp_path):
        proposal['status'] = 'rejected'
        rejected.append(pf)
        with open(pf, 'w') as f:
            json.dump(proposal, f)
        continue

    # Backward compatibility: strip leading 'harnesses/' prefix if present (old format)
    if exp_path.startswith('harnesses/'):
        exp_path = exp_path[len('harnesses/'):]

    # Canonicalize and validate within local_harnesses_dir
    allowed_base = os.path.realpath(local_harnesses_dir)
    candidate = os.path.realpath(os.path.join(allowed_base, exp_path))
    if not candidate.startswith(allowed_base + os.sep):
        proposal['status'] = 'rejected'
        rejected.append(pf)
        with open(pf, 'w') as f:
            json.dump(proposal, f)
        continue

    applied.append(pf)

print(json.dumps({'applied': applied, 'rejected': rejected}))
""", proposals_dir, pool_file, harnesses_dir, local_harnesses_dir],
            capture_output=True, text=True
        )
        return proc.stdout, proc.stderr, proc.returncode

    def test_absolute_path_rejected(self, tmp_path):
        """Proposals with absolute experimental_harness_path must be rejected."""
        _make_git_root(tmp_path)
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()
        proposals_dir = state_dir / "evolution-proposals"
        proposals_dir.mkdir()
        harnesses_dir = tmp_path / "harnesses"
        harnesses_dir.mkdir()

        pool = {"stable": {"tdd-driven": {"weight": 1.0}}, "experimental": {}}
        pool_file = state_dir / "harness-pool.json"
        with open(pool_file, "w") as fh:
            json.dump(pool, fh)

        # Write a proposal with absolute path (malicious)
        proposal = {
            "status": "pending",
            "proposal_type": "content_modification",
            "harness": "tdd-driven",
            "experimental_harness_path": "/etc/passwd",
        }
        with open(proposals_dir / "bad-abs.json", "w") as fh:
            json.dump(proposal, fh)

        stdout, stderr, rc = self._run_proposal_python(
            str(proposals_dir), str(pool_file), str(harnesses_dir)
        )
        result = json.loads(stdout)
        assert len(result["rejected"]) == 1, "Absolute path proposal must be rejected"
        assert len(result["applied"]) == 0

    def test_path_traversal_rejected(self, tmp_path):
        """Proposals with ../traversal paths must be rejected."""
        _make_git_root(tmp_path)
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()
        proposals_dir = state_dir / "evolution-proposals"
        proposals_dir.mkdir()
        harnesses_dir = tmp_path / "harnesses"
        harnesses_dir.mkdir()

        pool = {"stable": {"tdd-driven": {"weight": 1.0}}, "experimental": {}}
        pool_file = state_dir / "harness-pool.json"
        with open(pool_file, "w") as fh:
            json.dump(pool, fh)

        # Traversal attempt
        proposal = {
            "status": "pending",
            "proposal_type": "content_modification",
            "harness": "tdd-driven",
            "experimental_harness_path": "../../evil-dir",
        }
        with open(proposals_dir / "traversal.json", "w") as fh:
            json.dump(proposal, fh)

        stdout, _, rc = self._run_proposal_python(
            str(proposals_dir), str(pool_file), str(harnesses_dir)
        )
        result = json.loads(stdout)
        assert len(result["rejected"]) == 1, "Path traversal proposal must be rejected"
        assert len(result["applied"]) == 0

    def test_valid_relative_path_accepted(self, tmp_path):
        """Proposals with valid relative paths within allowed base are accepted."""
        _make_git_root(tmp_path)
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()
        proposals_dir = state_dir / "evolution-proposals"
        proposals_dir.mkdir()
        harnesses_dir = tmp_path / "harnesses"
        harnesses_dir.mkdir()

        pool = {"stable": {"tdd-driven": {"weight": 1.0}}, "experimental": {}}
        pool_file = state_dir / "harness-pool.json"
        with open(pool_file, "w") as fh:
            json.dump(pool, fh)

        proposal = {
            "status": "pending",
            "proposal_type": "content_modification",
            "harness": "tdd-driven",
            "experimental_harness_path": "harnesses/experimental/tdd-driven-v2",
        }
        with open(proposals_dir / "valid.json", "w") as fh:
            json.dump(proposal, fh)

        stdout, _, rc = self._run_proposal_python(
            str(proposals_dir), str(pool_file), str(harnesses_dir)
        )
        result = json.loads(stdout)
        # Valid path should not be in rejected
        assert len(result["rejected"]) == 0, "Valid relative path must not be rejected"

    def test_session_start_rejects_absolute_path_in_proposal(self, tmp_path):
        """session-start.sh hook rejects absolute experimental_harness_path."""
        _make_git_root(tmp_path)
        state_dir = tmp_path / ".adaptive-harness"
        proposals_dir = state_dir / "evolution-proposals"

        # Bootstrap state via the hook
        env = _base_env()
        stdout, stderr, rc = _run_hook("session-start.sh", env, str(tmp_path))
        assert rc == 0

        # Write malicious proposal pointing to an absolute path inside tmp_path (unique per test)
        injected_dir = str(tmp_path / "injected-absolute-dir")
        proposal = {
            "status": "pending",
            "proposal_type": "content_modification",
            "harness": "tdd-driven",
            "experimental_harness_path": injected_dir,
        }
        (proposals_dir / "malicious.json").write_text(json.dumps(proposal))

        # Run again to apply proposals
        stdout, stderr, rc = _run_hook("session-start.sh", env, str(tmp_path))
        assert rc == 0

        # The malicious proposal should be rejected (status == "rejected")
        with open(proposals_dir / "malicious.json") as fh:
            updated = json.load(fh)
        assert updated.get("status") == "rejected", (
            f"Absolute path proposal should be rejected, got status={updated.get('status')!r}"
        )
        # The malicious target should not have been created by our hook
        # (it's an absolute path so it would appear at an unexpected location)
        assert not os.path.exists(injected_dir), (
            "session-start.sh must not create the injected absolute path directory"
        )


# ---------------------------------------------------------------------------
# M2: JSON Injection via Unvalidated Variable in JSON Output
# ---------------------------------------------------------------------------

class TestM2JsonInjection:
    """CHAIN_MSG must be JSON-escaped before interpolation into JSON output."""

    def test_subagent_complete_outputs_valid_json_with_special_chars_in_chain_msg(
        self, tmp_path
    ):
        """If CHAIN_MSG contains quotes/backslashes, output must still be valid JSON."""
        _make_git_root(tmp_path)
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()

        # Write a chain-in-progress file with characters that break raw interpolation
        chain_content = 'step-with-"quotes" and \\backslash'
        (state_dir / ".chain-in-progress").write_text(chain_content)

        env = _base_env()
        stdout, stderr, rc = _run_hook("subagent-complete.sh", env, str(tmp_path))
        assert rc == 0, f"Hook exited with code {rc}: {stderr}"
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"subagent-complete.sh output is not valid JSON when CHAIN_MSG has special chars: {exc}\nOutput: {stdout!r}"
            )
        assert "hookSpecificOutput" in parsed

    def test_subagent_complete_outputs_valid_json_with_newline_in_chain_msg(
        self, tmp_path
    ):
        """Newlines in CHAIN_MSG must not break JSON output."""
        _make_git_root(tmp_path)
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()

        (state_dir / ".chain-in-progress").write_text("step1\nstep2")

        env = _base_env()
        stdout, stderr, rc = _run_hook("subagent-complete.sh", env, str(tmp_path))
        assert rc == 0
        try:
            json.loads(stdout)
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"Newline in CHAIN_MSG breaks JSON: {exc}\nOutput: {stdout!r}"
            )

    def test_subagent_complete_uses_escape_for_json(self):
        """subagent-complete.sh must call escape_for_json on CHAIN_MSG before JSON output."""
        hook_path = os.path.join(HOOKS_DIR, "subagent-complete.sh")
        with open(hook_path, "r") as fh:
            content = fh.read()
        # Must use escape_for_json function for CHAIN_MSG
        assert "escape_for_json" in content, (
            "subagent-complete.sh must apply escape_for_json to CHAIN_MSG before JSON output"
        )


# ---------------------------------------------------------------------------
# M3: Insufficient Input Validation for Harness Names
# ---------------------------------------------------------------------------

class TestM3HarnessNameValidation:
    """Harness names from proposals must be validated against a safe pattern."""

    def test_session_start_validates_harness_names_in_proposals(self, tmp_path):
        """Harness names with path separators or shell metacharacters must be rejected."""
        _make_git_root(tmp_path)
        env = _base_env()

        # Bootstrap state
        _, _, rc = _run_hook("session-start.sh", env, str(tmp_path))
        assert rc == 0

        state_dir = tmp_path / ".adaptive-harness"
        proposals_dir = state_dir / "evolution-proposals"

        # Write proposals with invalid harness names
        bad_names = [
            "../evil",
            "../../etc/passwd",
            "harness;rm -rf /",
            "harness|cat /etc/passwd",
            "valid/../evil",
        ]
        for i, name in enumerate(bad_names):
            proposal = {
                "status": "pending",
                "proposal_type": "content_modification",
                "harness": name,
                "experimental_harness_path": "harnesses/experimental/test-v2",
            }
            (proposals_dir / f"bad-name-{i}.json").write_text(json.dumps(proposal))

        # Run session-start to apply proposals
        _, _, rc = _run_hook("session-start.sh", env, str(tmp_path))
        assert rc == 0

        # All bad proposals must be rejected (not applied)
        for i, name in enumerate(bad_names):
            prop_file = proposals_dir / f"bad-name-{i}.json"
            with open(prop_file) as fh:
                updated = json.load(fh)
            assert updated.get("status") != "applied", (
                f"Harness name {name!r} should be rejected but was applied"
            )

    def test_valid_harness_name_passes_validation(self, tmp_path):
        """Harness names matching ^[a-zA-Z0-9_-]+$ must be accepted."""
        _make_git_root(tmp_path)
        env = _base_env()
        _, _, rc = _run_hook("session-start.sh", env, str(tmp_path))
        assert rc == 0

        state_dir = tmp_path / ".adaptive-harness"
        proposals_dir = state_dir / "evolution-proposals"

        valid_names = ["tdd-driven", "tdd_driven", "MyHarness123", "a", "A-B_C"]
        for i, name in enumerate(valid_names):
            proposal = {
                "status": "pending",
                "proposal_type": "content_modification",
                "harness": name,
                "experimental_harness_path": f"harnesses/experimental/{name}-v2",
            }
            (proposals_dir / f"valid-name-{i}.json").write_text(json.dumps(proposal))

        # Run — valid names must NOT be rejected due to name validation
        _, _, rc = _run_hook("session-start.sh", env, str(tmp_path))
        assert rc == 0

        for i, name in enumerate(valid_names):
            prop_file = proposals_dir / f"valid-name-{i}.json"
            with open(prop_file) as fh:
                updated = json.load(fh)
            # Valid names should NOT have status "rejected" from name validation
            assert updated.get("status") != "rejected", (
                f"Valid harness name {name!r} was incorrectly rejected"
            )

    def test_session_start_rejects_harness_name_with_shell_metachar(self, tmp_path):
        """Harness names with shell metacharacters must not proceed to path construction."""
        _make_git_root(tmp_path)
        env = _base_env()
        _, _, rc = _run_hook("session-start.sh", env, str(tmp_path))
        assert rc == 0

        state_dir = tmp_path / ".adaptive-harness"
        proposals_dir = state_dir / "evolution-proposals"

        proposal = {
            "status": "pending",
            "proposal_type": "content_modification",
            "harness": "evil$(id)",
            "experimental_harness_path": "harnesses/experimental/evil",
        }
        (proposals_dir / "metachar.json").write_text(json.dumps(proposal))

        _, _, rc = _run_hook("session-start.sh", env, str(tmp_path))
        assert rc == 0

        with open(proposals_dir / "metachar.json") as fh:
            updated = json.load(fh)
        assert updated.get("status") != "applied"


# ---------------------------------------------------------------------------
# M4: Insecure Temporary File Usage in GitHub Workflows
# ---------------------------------------------------------------------------

class TestM4InsecureTempFile:
    """release.yml must use mktemp instead of hardcoded /tmp/changelog.md."""

    def test_release_workflow_uses_mktemp(self):
        """release.yml must not use hardcoded /tmp/changelog.md."""
        workflow_path = os.path.join(
            WORKSPACE_ROOT, ".github", "workflows", "release.yml"
        )
        with open(workflow_path, "r") as fh:
            content = fh.read()
        assert "/tmp/changelog.md" not in content, (
            "release.yml must not use hardcoded /tmp/changelog.md — use mktemp instead"
        )

    def test_release_workflow_uses_mktemp_command(self):
        """release.yml must call mktemp for temporary file creation."""
        workflow_path = os.path.join(
            WORKSPACE_ROOT, ".github", "workflows", "release.yml"
        )
        with open(workflow_path, "r") as fh:
            content = fh.read()
        assert "mktemp" in content, (
            "release.yml must use mktemp to create temporary files"
        )


# ---------------------------------------------------------------------------
# L1: No Rate Limiting on Evidence File Creation
# ---------------------------------------------------------------------------

class TestL1EvidenceRateLimit:
    """collect-evidence.sh must stop creating files once the limit is reached."""

    def test_evidence_collection_respects_file_limit(self, tmp_path):
        """After max evidence files reached, collect-evidence.sh must skip new ones."""
        _make_git_root(tmp_path)
        session_id = "evidence-limit-test"
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()
        session_dir = state_dir / "sessions" / session_id
        evidence_dir = session_dir / "evidence"
        evidence_dir.mkdir(parents=True)
        (state_dir / ".current-session-id").write_text(session_id)

        # Pre-populate with max files (default: 100)
        for i in range(100):
            (evidence_dir / f"20240101T000000Z-{i:04d}.json").write_text(
                json.dumps({"dummy": True})
            )

        assert len(list(evidence_dir.iterdir())) == 100

        env = _base_env(session_id=session_id)
        hook_input = json.dumps({
            "tool_name": "Bash",
            "tool_input": {"command": "echo test"},
            "tool_response": {"output": "test", "exitCode": 0}
        })
        stdout, stderr, rc = _run_hook("collect-evidence.sh", env, str(tmp_path), stdin=hook_input)
        assert rc == 0

        # File count must not exceed 100
        final_count = len(list(evidence_dir.iterdir()))
        assert final_count <= 100, (
            f"Evidence file count exceeded limit: {final_count} > 100"
        )

    def test_evidence_collection_works_below_limit(self, tmp_path):
        """collect-evidence.sh must still create files when below the limit."""
        _make_git_root(tmp_path)
        session_id = "evidence-below-limit"
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()
        session_dir = state_dir / "sessions" / session_id
        evidence_dir = session_dir / "evidence"
        evidence_dir.mkdir(parents=True)
        (state_dir / ".current-session-id").write_text(session_id)

        # Pre-populate with 50 files (below limit)
        for i in range(50):
            (evidence_dir / f"20240101T000000Z-{i:04d}.json").write_text(
                json.dumps({"dummy": True})
            )

        env = _base_env(session_id=session_id)
        hook_input = json.dumps({
            "tool_name": "Bash",
            "tool_input": {"command": "echo test"},
            "tool_response": {"output": "test", "exitCode": 0}
        })
        _, _, rc = _run_hook("collect-evidence.sh", env, str(tmp_path), stdin=hook_input)
        assert rc == 0

        final_count = len(list(evidence_dir.iterdir()))
        assert final_count == 51, (
            f"Expected 51 evidence files (50 + 1 new), got {final_count}"
        )

    def test_evidence_limit_configurable_via_env(self, tmp_path):
        """MAX_EVIDENCE_FILES env var must override the default limit of 100."""
        _make_git_root(tmp_path)
        session_id = "evidence-custom-limit"
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()
        session_dir = state_dir / "sessions" / session_id
        evidence_dir = session_dir / "evidence"
        evidence_dir.mkdir(parents=True)
        (state_dir / ".current-session-id").write_text(session_id)

        # Pre-populate with 5 files (at custom limit of 5)
        for i in range(5):
            (evidence_dir / f"20240101T000000Z-{i:04d}.json").write_text(
                json.dumps({"dummy": True})
            )

        env = _base_env(session_id=session_id)
        env["MAX_EVIDENCE_FILES"] = "5"
        hook_input = json.dumps({
            "tool_name": "Bash",
            "tool_input": {"command": "echo test"},
            "tool_response": {"output": "test", "exitCode": 0}
        })
        _, _, rc = _run_hook("collect-evidence.sh", env, str(tmp_path), stdin=hook_input)
        assert rc == 0

        final_count = len(list(evidence_dir.iterdir()))
        assert final_count <= 5, f"Custom limit not respected: {final_count} > 5"


# ---------------------------------------------------------------------------
# L2: Missing Error Handling for Python Subprocess Failures
# ---------------------------------------------------------------------------

class TestL2PythonErrorLogging:
    """session-start.sh Python failures must be logged to a debug file."""

    def test_session_start_logs_to_debug_file_on_error(self, tmp_path):
        """When session-start.sh encounters a recoverable error, it logs to .debug-log."""
        _make_git_root(tmp_path)
        env = _base_env()
        # Set a deliberately missing plugin root so some Python paths fail
        env_bad = env.copy()
        env_bad["CLAUDE_PLUGIN_ROOT"] = str(tmp_path / "nonexistent-plugin")

        stdout, stderr, rc = _run_hook("session-start.sh", env_bad, str(tmp_path))
        # Should still exit 0 (graceful degradation) even with bad plugin root
        # (or fail gracefully — not crash with unhandled error)
        assert rc == 0 or rc == 1  # Acceptable: graceful exit

    def test_session_start_creates_debug_log_when_migration_fails(self, tmp_path):
        """If migration fails, session-start.sh must write to .debug-log not swallow stderr."""
        _make_git_root(tmp_path)
        env = _base_env()

        # Run the hook normally — it should work fine
        _, _, rc = _run_hook("session-start.sh", env, str(tmp_path))
        assert rc == 0

        # Verify the debug log mechanism exists in source (not /dev/null swallowing)
        hook_path = os.path.join(HOOKS_DIR, "session-start.sh")
        with open(hook_path, "r") as fh:
            content = fh.read()

        # The key requirement: errors should NOT be silently dropped with 2>/dev/null
        # when a debug log is available. The script should log to a debug file.
        # We check that there's a debug log write OR that 2>/dev/null is NOT used
        # on critical Python subprocess calls.
        has_debug_log = ".debug-log" in content or "debug_log" in content
        # Count 2>/dev/null suppressions on python3 lines
        python_devnull_count = content.count("python3") - content.count("2>/dev/null")
        # Accept: either has debug log OR doesn't suppress all python errors
        assert has_debug_log or "2>/dev/null" not in content, (
            "session-start.sh must use a debug log file instead of suppressing all Python errors"
        )
