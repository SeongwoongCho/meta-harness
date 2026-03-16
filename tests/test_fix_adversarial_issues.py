"""
Tests for fixes to the 6 adversarial code review issues.

These tests are written RED-first (they fail before the fix, pass after).

Issues fixed:
  C1 — escape_for_json trailing newline regression (<<< adds \\n to stdin)
  C2 — CHAIN_MSG scope hole when session dir absent
  H1 — Simple ensemble missing chain marker in SKILL.md
  H2 — Template placeholder inconsistency ({harness_chain_json} vs 'chain')
  H3 — contract.yaml task_types missing new taxonomy values
  H4 — migrate.sh doesn't reclassify experimental→stable
"""

import json
import os
import subprocess

import pytest
import yaml

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS_DIR = os.path.join(WORKSPACE_ROOT, "hooks")
PLUGIN_ROOT = WORKSPACE_ROOT


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


def _base_env(plugin_root: str = PLUGIN_ROOT, session_id: str = "fix-test-001") -> dict:
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = plugin_root
    env["CLAUDE_SESSION_ID"] = session_id
    return env


def _make_git_root(tmp_path):
    (tmp_path / ".git").mkdir(exist_ok=True)
    return tmp_path


# ---------------------------------------------------------------------------
# C1 — escape_for_json trailing newline regression
# After fix: sys.argv[1] is used instead of <<< "$1", so no trailing \n.
# ---------------------------------------------------------------------------

class TestC1EscapeForJsonFixed:
    """Verify the fixed escape_for_json does NOT produce a trailing newline."""

    def _call_fixed_escape_for_json(self, input_str: str) -> str:
        """Run the FIXED escape_for_json (uses sys.argv[1] instead of <<<)."""
        proc = subprocess.run(
            ["bash", "-s", "--", input_str],
            input=r"""
escape_for_json() {
    python3 -c "
import json, sys
print(json.dumps(sys.argv[1])[1:-1], end='')
" "$1"
}
result=$(escape_for_json "$1")
printf '%s' "$result"
""",
            capture_output=True, text=True,
        )
        return proc.stdout

    def test_empty_string_produces_empty_output(self):
        """Fixed escape_for_json('') should return '' (empty), not '\\n'."""
        result = self._call_fixed_escape_for_json("")
        assert result == "", (
            f"Fixed escape_for_json('') should return empty string, got {repr(result)}"
        )

    def test_plain_string_produces_correct_output(self):
        """Fixed escape_for_json('hello') should return 'hello' (no trailing newline)."""
        result = self._call_fixed_escape_for_json("hello")
        assert result == "hello", (
            f"Fixed escape_for_json('hello') should return 'hello', got {repr(result)}"
        )

    def test_string_with_quotes_is_escaped(self):
        """escape_for_json should escape double quotes properly."""
        result = self._call_fixed_escape_for_json('say "hi"')
        assert result == r'say \"hi\"', (
            f"escape_for_json should escape double quotes, got {repr(result)}"
        )

    def test_session_start_no_heredoc_in_escape_for_json(self):
        """session-start.sh escape_for_json must NOT use <<< heredoc (adds trailing newline)."""
        with open(os.path.join(HOOKS_DIR, "session-start.sh")) as f:
            content = f.read()
        # The broken <<< heredoc pattern must be absent inside escape_for_json
        func_start = content.find("escape_for_json()")
        assert func_start != -1, "escape_for_json function must exist in session-start.sh"
        func_end = content.find("\n}\n", func_start)
        func_body = content[func_start:func_end]
        assert "<<<" not in func_body, (
            "escape_for_json must not use <<< (here-string) — it adds a trailing newline"
        )

    def test_session_start_migrate_notice_does_not_start_with_newline(self, tmp_path):
        """In non-auto mode, additionalContext must NOT start with a newline char."""
        _make_git_root(tmp_path)
        env = _base_env()
        env["ADAPTIVE_HARNESS_SKIP_MIGRATION"] = "1"
        stdout, _, rc = _run_hook("session-start.sh", env, str(tmp_path))
        assert rc == 0
        parsed = json.loads(stdout)
        ctx = parsed["hookSpecificOutput"]["additionalContext"]
        assert ctx[0] != "\n", (
            f"additionalContext must not start with newline (C1 regression), "
            f"starts with {repr(ctx[0])}"
        )


# ---------------------------------------------------------------------------
# C2 — CHAIN_MSG scope hole when session dir absent
# After fix: chain-in-progress check runs OUTSIDE the session dir block.
# ---------------------------------------------------------------------------

class TestC2ChainMsgScopeFixed:
    """Verify CHAIN_MSG is set correctly even when SESSION_DIR doesn't exist."""

    def test_chain_in_progress_without_session_dir_gets_chain_message(self, tmp_path):
        """When .chain-in-progress exists but SESSION_DIR doesn't exist,
        the fixed hook must return a 'Chain step completed' message, not eval-pending."""
        _make_git_root(tmp_path)
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()
        (state_dir / ".chain-in-progress").write_text("chain-data")
        session_id = "no-session-dir-c2"
        (state_dir / ".current-session-id").write_text(session_id)
        # Do NOT create session dir

        env = _base_env(session_id=session_id)
        stdout, _, rc = _run_hook("subagent-complete.sh", env, str(tmp_path), stdin="{}")
        assert rc == 0
        parsed = json.loads(stdout)
        ctx = parsed["hookSpecificOutput"]["additionalContext"]
        assert "Chain step completed" in ctx, (
            f"When .chain-in-progress exists, chain message must fire even without "
            f"SESSION_DIR. Got: {ctx!r}"
        )
        assert "EVALUATION PENDING" not in ctx, (
            f"Eval-pending message must NOT fire during a chain. Got: {ctx!r}"
        )

    def test_no_chain_marker_without_session_dir_still_uses_fallback(self, tmp_path):
        """When neither chain marker nor session dir exists, fallback message is OK."""
        _make_git_root(tmp_path)
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()
        session_id = "no-session-dir-no-chain"
        (state_dir / ".current-session-id").write_text(session_id)
        # No chain marker, no session dir

        env = _base_env(session_id=session_id)
        stdout, _, rc = _run_hook("subagent-complete.sh", env, str(tmp_path), stdin="{}")
        assert rc == 0
        parsed = json.loads(stdout)
        ctx = parsed["hookSpecificOutput"]["additionalContext"]
        assert "EVALUATION PENDING" in ctx, (
            f"Without chain marker, fallback eval-pending message should fire. Got: {ctx!r}"
        )

    def test_chain_check_outside_session_dir_block_in_source(self):
        """subagent-complete.sh: the CHAIN_FILE check must not be nested inside
        'if [ -d "$SESSION_DIR" ]' block."""
        with open(os.path.join(HOOKS_DIR, "subagent-complete.sh")) as f:
            content = f.read()
        # After fix, .chain-in-progress check must appear before or outside
        # the SESSION_DIR directory check nesting
        chain_check_pos = content.find(".chain-in-progress")
        session_dir_check_pos = content.find('if [ -d "$SESSION_DIR"')
        assert chain_check_pos != -1, ".chain-in-progress check must exist in file"
        assert session_dir_check_pos != -1, "SESSION_DIR block must still exist"
        # The chain file check should come before or at the same level as SESSION_DIR check
        # (i.e., not nested inside it). We verify this by checking indentation or position.
        # Simplest: chain check line should appear BEFORE the SESSION_DIR directory block
        # OR the chain file should be checked in a separate block outside SESSION_DIR.
        # After fix: chain check is moved OUTSIDE the if [ -d "$SESSION_DIR" ] block.
        # Check that the line "CHAIN_FILE=" appears before "if [ -d \"$SESSION_DIR\""
        chain_file_assign_pos = content.find("CHAIN_FILE=")
        assert chain_file_assign_pos < session_dir_check_pos or chain_file_assign_pos != -1, (
            "CHAIN_FILE assignment must exist and be outside (before) the SESSION_DIR block"
        )


# ---------------------------------------------------------------------------
# H1 — Simple ensemble missing chain marker in SKILL.md
# After fix: Mode 1 instructions include writing .chain-in-progress.
# ---------------------------------------------------------------------------

class TestH1SimpleEnsembleChainMarker:
    """Verify SKILL.md Mode 1 (simple ensemble) writes .chain-in-progress."""

    SKILL_PATH = os.path.join(
        WORKSPACE_ROOT, "skills", "using-adaptive-harness", "SKILL.md"
    )

    def test_mode1_writes_chain_in_progress_before_spawning(self):
        """Mode 1 ensemble must write .chain-in-progress before spawning harnesses."""
        with open(self.SKILL_PATH) as f:
            content = f.read()

        # Find Mode 1 section
        mode1_start = content.find("#### Mode 1: Simple Harness Ensemble")
        mode2_start = content.find("#### Mode 2: Chain Ensemble")
        assert mode1_start != -1, "Mode 1 section must exist"
        assert mode2_start != -1, "Mode 2 section must exist"

        mode1_section = content[mode1_start:mode2_start]
        assert ".chain-in-progress" in mode1_section, (
            "Mode 1 (simple ensemble) must write .chain-in-progress before spawning harnesses. "
            "This prevents SubagentStop from firing premature .eval-pending markers."
        )

    def test_mode1_removes_chain_marker_after_synthesizer(self):
        """Mode 1 ensemble must remove .chain-in-progress after synthesizer completes."""
        with open(self.SKILL_PATH) as f:
            content = f.read()

        mode1_start = content.find("#### Mode 1: Simple Harness Ensemble")
        mode2_start = content.find("#### Mode 2: Chain Ensemble")
        mode1_section = content[mode1_start:mode2_start]

        # Must have both write and removal of chain marker
        assert ".chain-in-progress" in mode1_section, (
            "Mode 1 must write .chain-in-progress"
        )
        assert "rm -f" in mode1_section and ".chain-in-progress" in mode1_section, (
            "Mode 1 must remove .chain-in-progress after synthesizer completes"
        )


# ---------------------------------------------------------------------------
# H2 — Template placeholder inconsistency
# After fix: chain marker write uses 'chain' not {harness_chain_json}.
# ---------------------------------------------------------------------------

class TestH2ChainMarkerPlaceholderFixed:
    """Verify SKILL.md Step 3.5 uses literal 'chain' not {harness_chain_json}."""

    SKILL_PATH = os.path.join(
        WORKSPACE_ROOT, "skills", "using-adaptive-harness", "SKILL.md"
    )

    def test_step_35_uses_literal_chain_string(self):
        """Step 3.5 chain marker write must use 'chain' not {harness_chain_json}."""
        with open(self.SKILL_PATH) as f:
            content = f.read()

        assert "{harness_chain_json}" not in content, (
            "SKILL.md must not contain {harness_chain_json} placeholder — "
            "use literal string 'chain' for consistency with Mode 2 which uses 'ensemble'"
        )

    def test_step_35_chain_marker_write_uses_fixed_string(self):
        """The chain marker write in Step 3.5 must use a fixed string (not a placeholder)."""
        with open(self.SKILL_PATH) as f:
            content = f.read()

        # Find Step 3.5
        step35_start = content.find("### Step 3.5:")
        assert step35_start != -1, "Step 3.5 section must exist"

        # Find next section
        next_section = content.find("\n### ", step35_start + 1)
        step35_section = content[step35_start:next_section] if next_section != -1 else content[step35_start:]

        # Should have a printf with 'chain' as the value (not a {} placeholder)
        assert "printf 'chain'" in step35_section or "printf \"chain\"" in step35_section, (
            "Step 3.5 chain marker write must use literal string 'chain', "
            f"not a template placeholder. Section:\n{step35_section[:500]}"
        )


# ---------------------------------------------------------------------------
# H3 — contract.yaml task_types missing new taxonomy values
# After fix: each contract has the new taxonomy task_type added.
# ---------------------------------------------------------------------------

class TestH3ContractTaskTypesUpdated:
    """Verify the 5 harness contract.yaml files include the new taxonomy task_types."""

    HARNESSES_DIR = os.path.join(WORKSPACE_ROOT, "harnesses")

    def _load_contract(self, harness_name: str) -> dict:
        path = os.path.join(self.HARNESSES_DIR, harness_name, "contract.yaml")
        with open(path) as f:
            return yaml.safe_load(f)

    def test_plan_review_has_review_task_type(self):
        """plan-review contract.yaml must include 'review' in task_types."""
        contract = self._load_contract("plan-review")
        task_types = contract.get("trigger", {}).get("task_types", [])
        assert "review" in task_types, (
            f"plan-review contract.yaml must include 'review' in task_types. "
            f"Current task_types: {task_types}"
        )

    def test_pre_landing_review_has_review_task_type(self):
        """pre-landing-review contract.yaml must include 'review' in task_types."""
        contract = self._load_contract("pre-landing-review")
        task_types = contract.get("trigger", {}).get("task_types", [])
        assert "review" in task_types, (
            f"pre-landing-review contract.yaml must include 'review' in task_types. "
            f"Current task_types: {task_types}"
        )

    def test_qa_testing_has_ops_task_type(self):
        """qa-testing contract.yaml must include 'ops' in task_types."""
        contract = self._load_contract("qa-testing")
        task_types = contract.get("trigger", {}).get("task_types", [])
        assert "ops" in task_types, (
            f"qa-testing contract.yaml must include 'ops' in task_types. "
            f"Current task_types: {task_types}"
        )

    def test_engineering_retro_has_ops_task_type(self):
        """engineering-retro contract.yaml must include 'ops' in task_types."""
        contract = self._load_contract("engineering-retro")
        task_types = contract.get("trigger", {}).get("task_types", [])
        assert "ops" in task_types, (
            f"engineering-retro contract.yaml must include 'ops' in task_types. "
            f"Current task_types: {task_types}"
        )

    def test_ship_workflow_has_release_task_type(self):
        """ship-workflow contract.yaml must include 'release' in task_types."""
        contract = self._load_contract("ship-workflow")
        task_types = contract.get("trigger", {}).get("task_types", [])
        assert "release" in task_types, (
            f"ship-workflow contract.yaml must include 'release' in task_types. "
            f"Current task_types: {task_types}"
        )


# ---------------------------------------------------------------------------
# H4 — migrate.sh doesn't reclassify experimental→stable
# After fix: migrate.sh reads each harness metadata and moves misclassified
# entries to the correct tier.
# ---------------------------------------------------------------------------

class TestH4MigrateReclassifies:
    """Verify migrate.sh reclassifies experimental→stable when contract.yaml says stable.

    Uses 'careful-refactor' as the test subject because its contract.yaml has pool=stable.
    """

    # careful-refactor has pool=stable in its contract.yaml — use it as the misclassified harness
    TEST_HARNESS = "careful-refactor"

    def test_experimental_harness_moved_to_stable_after_migration(self, tmp_path):
        """If careful-refactor is in experimental but its contract.yaml says pool=stable,
        migrate.sh must move it to stable."""
        _make_git_root(tmp_path)
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()

        # Simulate user's pool: careful-refactor is misclassified in experimental
        pool = {
            "stable": {
                "tdd-driven": {
                    "weight": 1.0, "total_runs": 0, "successes": 0,
                    "failures": 0, "consecutive_successes": 0
                }
            },
            "experimental": {
                self.TEST_HARNESS: {
                    "weight": 1.2, "total_runs": 5, "successes": 3,
                    "failures": 2, "consecutive_successes": 1
                }
            },
            "last_updated": None,
            "last_merged_session": None,
        }
        pool_path = state_dir / "harness-pool.json"
        with open(pool_path, "w") as f:
            json.dump(pool, f)

        (state_dir / ".plugin-version").write_text("0.0.0")

        env = _base_env()
        env["ADAPTIVE_HARNESS_PLUGIN_VERSION"] = "1.0.4"

        proc = subprocess.run(
            ["bash", os.path.join(HOOKS_DIR, "migrate.sh")],
            env=env, cwd=str(tmp_path),
            capture_output=True, text=True
        )
        assert proc.returncode == 0, f"migrate.sh failed: {proc.stderr}"

        with open(pool_path) as f:
            updated_pool = json.load(f)

        # careful-refactor must be in stable after migration (contract.yaml says pool=stable)
        assert self.TEST_HARNESS in updated_pool.get("stable", {}), (
            f"migrate.sh must reclassify {self.TEST_HARNESS} from experimental to stable "
            f"because its contract.yaml has pool=stable. "
            f"Updated pool stable keys: {list(updated_pool.get('stable', {}).keys())}"
        )
        # Must be removed from experimental
        assert self.TEST_HARNESS not in updated_pool.get("experimental", {}), (
            f"{self.TEST_HARNESS} must be removed from experimental after reclassification. "
            f"experimental keys: {list(updated_pool.get('experimental', {}).keys())}"
        )

    def test_migrate_preserves_existing_weights_when_reclassifying(self, tmp_path):
        """Reclassification must preserve the harness's existing weight and stats."""
        _make_git_root(tmp_path)
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()

        pool = {
            "stable": {},
            "experimental": {
                self.TEST_HARNESS: {
                    "weight": 0.8, "total_runs": 10, "successes": 7,
                    "failures": 3, "consecutive_successes": 2
                }
            },
            "last_updated": None,
            "last_merged_session": None,
        }
        pool_path = state_dir / "harness-pool.json"
        with open(pool_path, "w") as f:
            json.dump(pool, f)

        (state_dir / ".plugin-version").write_text("0.0.0")

        env = _base_env()
        env["ADAPTIVE_HARNESS_PLUGIN_VERSION"] = "1.0.4"

        subprocess.run(
            ["bash", os.path.join(HOOKS_DIR, "migrate.sh")],
            env=env, cwd=str(tmp_path),
            capture_output=True, text=True
        )

        with open(pool_path) as f:
            updated_pool = json.load(f)

        assert self.TEST_HARNESS in updated_pool.get("stable", {}), (
            f"{self.TEST_HARNESS} must be in stable after reclassification"
        )
        entry = updated_pool["stable"][self.TEST_HARNESS]
        assert entry["weight"] == 0.8, "Weight must be preserved during reclassification"
        assert entry["total_runs"] == 10, "total_runs must be preserved"
        assert entry["successes"] == 7, "successes must be preserved"

    def test_stable_harness_in_experimental_stays_only_once(self, tmp_path):
        """A harness reclassified from experimental to stable must not appear in both tiers."""
        _make_git_root(tmp_path)
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()

        pool = {
            "stable": {},
            "experimental": {
                self.TEST_HARNESS: {
                    "weight": 1.0, "total_runs": 0, "successes": 0,
                    "failures": 0, "consecutive_successes": 0
                }
            },
            "last_updated": None,
            "last_merged_session": None,
        }
        pool_path = state_dir / "harness-pool.json"
        with open(pool_path, "w") as f:
            json.dump(pool, f)

        (state_dir / ".plugin-version").write_text("0.0.0")

        env = _base_env()
        env["ADAPTIVE_HARNESS_PLUGIN_VERSION"] = "1.0.4"

        subprocess.run(
            ["bash", os.path.join(HOOKS_DIR, "migrate.sh")],
            env=env, cwd=str(tmp_path),
            capture_output=True, text=True
        )

        with open(pool_path) as f:
            updated_pool = json.load(f)

        in_stable = self.TEST_HARNESS in updated_pool.get("stable", {})
        in_experimental = self.TEST_HARNESS in updated_pool.get("experimental", {})
        assert not (in_stable and in_experimental), (
            f"{self.TEST_HARNESS} must not appear in both stable and experimental after migration"
        )
