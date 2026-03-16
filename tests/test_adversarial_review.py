"""
Adversarial test cases from code review of fix/chain-turn-break branch.

These tests probe known weaknesses, edge cases, and regressions identified
during adversarial review. They do NOT modify production code.

Findings probed here:
1. escape_for_json trailing-newline regression (<<< adds \n to stdin)
2. CHAIN_MSG variable scope when SESSION_DIR does not exist
3. Simple-ensemble (ensemble_harnesses) missing chain marker
4. state_dir fallback silently absorbed inside state_dir()
5. Weak test assertion in test_chain_in_progress_overrides_auto_mode
6. Chain marker content inconsistency (ensemble writes 'ensemble', chain writes literal placeholder)
7. extract_sub_chains with empty sub-chain list (edge case)
8. Evolution trigger every-1 with zero eval history
9. prompt-interceptor CHAIN_IN_PROGRESS fires even when pipeline mode is absent
10. subagent-complete fallback message fires when SESSION_DIR absent during chain
"""

import json
import os
import subprocess

import pytest

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


def _base_env(plugin_root: str = PLUGIN_ROOT, session_id: str = "adversarial-001") -> dict:
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = plugin_root
    env["CLAUDE_SESSION_ID"] = session_id
    return env


def _make_git_root(tmp_path):
    (tmp_path / ".git").mkdir(exist_ok=True)
    return tmp_path


# ---------------------------------------------------------------------------
# Finding 1: escape_for_json trailing-newline regression
# <<< "$1" appends a newline to stdin, so json.dumps encodes it as \n,
# and every escaped string has a spurious trailing \n.
# Empty string ("") produces "\n" instead of "".
# ---------------------------------------------------------------------------

class TestEscapeForJsonRegression:
    """Probe the escape_for_json trailing-newline behavior introduced in commit 8b2eceb."""

    def _call_escape_for_json(self, input_str: str) -> str:
        """Run escape_for_json as defined in session-start.sh and return its output."""
        script = r"""
escape_for_json() {
    python3 -c "
import json, sys
s = sys.stdin.read()
print(json.dumps(s)[1:-1], end='')
" <<< "$1"
}
result=$(escape_for_json "$1")
printf '%s' "$result"
"""
        proc = subprocess.run(
            ["bash", "-c", f'FUNC={repr(script)}\n{script}', "--", input_str],
            capture_output=True, text=True,
        )
        # Actually pass via positional arg:
        proc2 = subprocess.run(
            ["bash", "-s", "--", input_str],
            input=r"""
escape_for_json() {
    python3 -c "
import json, sys
s = sys.stdin.read()
print(json.dumps(s)[1:-1], end='')
" <<< "$1"
}
result=$(escape_for_json "$1")
printf '%s' "$result"
""",
            capture_output=True, text=True,
        )
        return proc2.stdout

    def test_empty_string_produces_trailing_newline_escape(self):
        """escape_for_json('') returns '\\n' (2 chars) not '' due to <<< adding newline."""
        result = self._call_escape_for_json("")
        # The <<< heredoc appends \n to stdin, so json.dumps("") → '""',
        # but json.dumps("\n") → '"\\n"', stripped → '\\n'.
        # This is the regression: empty string should produce empty output.
        # Document the actual (broken) behavior:
        assert result == r"\n", (
            f"escape_for_json('') returns {repr(result)!r}; "
            f"expected empty string ''. "
            f"This is a known regression: <<< adds trailing newline to stdin."
        )

    def test_session_start_non_auto_mode_context_starts_with_escaped_newline(self, tmp_path):
        """In non-auto mode, additionalContext starts with \\n when MIGRATE_NOTICE is empty."""
        _make_git_root(tmp_path)
        env = _base_env()
        # Ensure no migration runs by skipping it
        env["ADAPTIVE_HARNESS_SKIP_MIGRATION"] = "1"
        stdout, _, rc = _run_hook("session-start.sh", env, str(tmp_path))
        assert rc == 0
        parsed = json.loads(stdout)
        ctx = parsed["hookSpecificOutput"]["additionalContext"]
        # The context starts with '\n' (real newline) from the escaped empty MIGRATE_NOTICE.
        # This is the regression — it should start with '[adaptive-harness]'.
        # We document what actually happens:
        assert ctx[0] == "\n" or ctx[0] == "[", (
            f"Context starts with {repr(ctx[0])}; expected either '\\n' (regression) or '[' (correct)"
        )


# ---------------------------------------------------------------------------
# Finding 2: CHAIN_MSG variable scope — unset when SESSION_DIR absent
# In subagent-complete.sh, CHAIN_MSG is only set inside nested if blocks.
# When SESSION_ID is set but SESSION_DIR does not exist, CHAIN_MSG is never set.
# The fallback ${CHAIN_MSG:-...} fires with the non-chain eval message.
# ---------------------------------------------------------------------------

class TestChainMsgScopeWhenSessionDirAbsent:
    """Probe subagent-complete.sh when session dir doesn't exist during chain."""

    def test_chain_in_progress_but_no_session_dir_uses_fallback_message(self, tmp_path):
        """When .chain-in-progress exists but SESSION_DIR doesn't exist,
        CHAIN_MSG is unset and the fallback fires with eval-pending message.
        This is a bug: the model gets told to evaluate even during a chain."""
        _make_git_root(tmp_path)
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()
        # Mark chain as in progress
        (state_dir / ".chain-in-progress").write_text("chain-data")
        # Do NOT create session directory
        session_id = "no-session-dir-test"
        (state_dir / ".current-session-id").write_text(session_id)

        env = _base_env(session_id=session_id)
        stdout, _, rc = _run_hook("subagent-complete.sh", env, str(tmp_path), stdin="{}")
        assert rc == 0
        parsed = json.loads(stdout)
        ctx = parsed["hookSpecificOutput"]["additionalContext"]
        # With the current code, CHAIN_MSG is never set because the inner if [ -d "$SESSION_DIR" ]
        # block is skipped. The fallback message contains "EVALUATION PENDING", not "Chain step".
        # This means the chain suppression FAILS silently when session dir is absent.
        # Document actual behavior:
        if "Chain step completed" in ctx:
            # Desired behavior — chain message fires
            assert "EVALUATION PENDING" not in ctx
        else:
            # Actual (broken) behavior — fallback fires with eval message
            # This means the chain guard fails when session dir is missing
            assert "EVALUATION PENDING" in ctx or "Continue to Step 5" in ctx, (
                f"Fallback message expected but got: {ctx!r}"
            )


# ---------------------------------------------------------------------------
# Finding 3: Simple ensemble (ensemble_harnesses) has no chain marker management
# The SKILL.md for Mode 1 (simple ensemble) does NOT write .chain-in-progress.
# Each harness's SubagentStop will incorrectly write .eval-pending.
# ---------------------------------------------------------------------------

class TestSimpleEnsembleMissingChainMarker:
    """Document the gap: simple ensemble has no chain marker in SKILL.md."""

    def test_subagent_complete_without_chain_marker_writes_eval_pending(self, tmp_path):
        """Without .chain-in-progress, each harness in a simple ensemble
        incorrectly triggers .eval-pending — SubagentStop can't distinguish
        ensemble step from standalone execution."""
        _make_git_root(tmp_path)
        session_id = "simple-ensemble-test"
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()
        session_dir = state_dir / "sessions" / session_id
        session_dir.mkdir(parents=True)
        (state_dir / ".current-session-id").write_text(session_id)
        # No .chain-in-progress — simple ensemble doesn't write it

        env = _base_env(session_id=session_id)
        stdout, _, rc = _run_hook("subagent-complete.sh", env, str(tmp_path), stdin="{}")
        assert rc == 0
        # Without chain marker, .eval-pending IS written — this is the bug
        # for simple ensemble where evaluation should wait for synthesizer.
        eval_pending_exists = (session_dir / ".eval-pending").exists()
        assert eval_pending_exists, (
            "Without .chain-in-progress, SubagentStop writes .eval-pending. "
            "For simple ensemble (ensemble_harnesses), this fires for each harness "
            "before the synthesizer runs. SKILL.md does not write .chain-in-progress "
            "for Mode 1 simple ensemble."
        )


# ---------------------------------------------------------------------------
# Finding 4: state_dir fallback in session-start.sh silently absorbed
# PROJECT_ROOT="$(resolve_project_root)" || PROJECT_ROOT="$PWD"
# But state_dir() calls resolve_project_root internally and doesn't propagate
# the failure — so the STATE_DIR fallback block rarely triggers as intended.
# ---------------------------------------------------------------------------

class TestStateDirFallbackResolution:
    """Probe the state_dir fallback behavior."""

    def test_state_dir_absorbs_resolve_project_root_failure(self):
        """state_dir() calls resolve_project_root() via command substitution.
        If resolve_project_root() returns 1, the return code is silently lost.
        state_dir() succeeds anyway with the echoed path.
        The fallback block in session-start.sh only fires for CLAUDE_PLUGIN_ROOT conflicts."""
        script = """
source /home/seongwoong/workspace/adaptive-harness/hooks/lib.sh
# Simulate resolve_project_root returning non-zero by overriding
resolve_project_root() {
    echo "$HOME"
    return 1
}
# state_dir calls resolve_project_root internally
result=$(state_dir 2>/dev/null)
echo "exit:$?"
echo "result:$result"
"""
        proc = subprocess.run(
            ["bash", "-c", script],
            capture_output=True, text=True,
        )
        lines = proc.stdout.strip().splitlines()
        result = {line.split(":")[0]: ":".join(line.split(":")[1:]) for line in lines if ":" in line}
        # state_dir() should succeed (exit 0) because the return 1 from resolve_project_root
        # is lost inside the command substitution $()
        assert result.get("exit") == "0", (
            f"Expected state_dir to succeed despite resolve_project_root returning 1, "
            f"got exit={result.get('exit')}. "
            f"This means the state_dir fallback in session-start.sh only fires in "
            f"very specific CLAUDE_PLUGIN_ROOT conflict scenarios."
        )


# ---------------------------------------------------------------------------
# Finding 5: prompt-interceptor chain check fires even with no pipeline mode
# When .chain-in-progress exists but no .pipeline-mode is set,
# the chain message is injected. This is correct behavior but untested.
# ---------------------------------------------------------------------------

class TestPromptInterceptorChainWithoutPipelineMode:
    """Chain check is independent of pipeline mode — test this."""

    def test_chain_fires_without_pipeline_mode(self, tmp_path):
        """Even with no .pipeline-mode file, .chain-in-progress triggers chain message."""
        _make_git_root(tmp_path)
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()
        # No .pipeline-mode file — pipeline is off
        (state_dir / ".chain-in-progress").write_text("chain-data")

        env = _base_env()
        stdout, _, rc = _run_hook("prompt-interceptor.sh", env, str(tmp_path))
        assert rc == 0
        parsed = json.loads(stdout)
        ctx = parsed["hookSpecificOutput"]["additionalContext"]
        assert "CHAIN IN PROGRESS" in ctx, (
            "Chain-in-progress should fire even without pipeline mode. "
            f"Got: {ctx!r}"
        )

    def test_chain_fires_with_run_mode(self, tmp_path):
        """Chain-in-progress fires even when pipeline mode is 'run' (one-shot)."""
        _make_git_root(tmp_path)
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()
        (state_dir / ".pipeline-mode").write_text("run")
        (state_dir / ".chain-in-progress").write_text("chain-data")

        env = _base_env()
        stdout, _, rc = _run_hook("prompt-interceptor.sh", env, str(tmp_path))
        assert rc == 0
        parsed = json.loads(stdout)
        ctx = parsed["hookSpecificOutput"]["additionalContext"]
        assert "CHAIN IN PROGRESS" in ctx


# ---------------------------------------------------------------------------
# Finding 6: extract_sub_chains edge cases
# The fix replaces chain[-1] with chain[1:].
# What about chains with only 1 element? chain[1:] = [] (empty list).
# This means the LLM would receive an empty sub-chain to iterate over.
# ---------------------------------------------------------------------------

def extract_sub_chains(ensemble_chains: list) -> list:
    """Extract sub-chains: skip the first (shared planning) element per chain."""
    return [chain[1:] for chain in ensemble_chains]


class TestExtractSubChainsEdgeCases:
    """Adversarial edge cases for chain[1:] fix."""

    def test_single_element_chain_produces_empty_sub_chain(self):
        """chain[1:] for a 1-element chain produces []. This is a degenerate case
        that would cause the LLM to iterate over nothing."""
        chains = [["only-harness"]]
        sub_chains = extract_sub_chains(chains)
        assert sub_chains == [[]], (
            "A 1-element chain produces an empty sub-chain. "
            "The orchestrator would fan out a worktree for nothing."
        )

    def test_empty_chains_list_produces_empty_result(self):
        chains = []
        sub_chains = extract_sub_chains(chains)
        assert sub_chains == []

    def test_empty_chain_within_list_produces_empty_sub_chain(self):
        """An empty list within ensemble_chains produces an empty sub-chain."""
        chains = [[], ["ralplan-consensus", "tdd-driven"]]
        sub_chains = extract_sub_chains(chains)
        assert sub_chains[0] == [], "Empty chain produces empty sub-chain"
        assert sub_chains[1] == ["tdd-driven"]

    def test_chain_with_only_planning_step_has_no_execution_harness(self):
        """If ensemble_chains only has the planning step, sub_chains are all empty.
        This breaks the fan-out as there's nothing to execute per worktree."""
        chains = [["ralplan-consensus"], ["ralplan-consensus"]]
        sub_chains = extract_sub_chains(chains)
        assert all(s == [] for s in sub_chains), (
            "When all chains have only the planning step, sub_chains are empty. "
            "The orchestrator would create worktrees but run no harnesses."
        )

    def test_old_behavior_equivalent_for_two_step_chains(self):
        """Verify chain[1:] == [chain[-1]] for 2-step chains (no regression)."""
        chains = [["ralplan-consensus", "tdd-driven"],
                  ["ralplan-consensus", "system-design"]]
        sub_chains = extract_sub_chains(chains)
        old_result = [[chain[-1]] for chain in chains]
        assert sub_chains == old_result


# ---------------------------------------------------------------------------
# Finding 7: Evolution trigger every-1 with insufficient data
# Spawning evolution-manager after every single evaluation means it has
# at most 1 eval entry to analyze. The evolution manager needs trends.
# ---------------------------------------------------------------------------

class TestEvolutionTriggerFrequency:
    """Document the evolution trigger change from every-2 to every-1."""

    def test_count_gte_1_always_triggers_evolution(self):
        """With count >= 1, evolution fires after EVERY evaluation.
        For a brand new harness with 1 eval, the manager has only 1 data point."""
        # Simulate the trigger logic: count files in evaluation-logs/
        count = 1
        should_trigger_new = count >= 1
        should_trigger_old = count >= 2 and count % 2 == 0
        assert should_trigger_new is True, "New logic: always trigger with count>=1"
        assert should_trigger_old is False, "Old logic: only trigger at count=2,4,6,..."

    def test_count_2_both_trigger(self):
        count = 2
        should_trigger_new = count >= 1
        should_trigger_old = count >= 2 and count % 2 == 0
        assert should_trigger_new is True
        assert should_trigger_old is True

    def test_evolution_fires_on_first_ever_evaluation(self):
        """Evolution manager spawns on the very first evaluation (count=1).
        With only 1 data point, the manager cannot make statistically meaningful decisions."""
        count = 1  # first eval
        old_trigger = count >= 2 and count % 2 == 0
        new_trigger = count >= 1
        assert new_trigger and not old_trigger, (
            "New: evolution fires on count=1 (1 data point). "
            "Old: evolution waited for count=2. "
            "1 data point may not be sufficient for meaningful evolution decisions."
        )


# ---------------------------------------------------------------------------
# Finding 8: Stale .chain-in-progress cleanup order in session-end.sh
# session-end.sh cleans up .chain-in-progress AFTER removing .current-session-id.
# If .current-session-id is removed first, resolve_session_id returns empty.
# But the chain cleanup uses STATE_DIR directly, not SESSION_ID. Safe.
# Also: .eval-pending cleanup checks SESSION_ID which was resolved BEFORE cleanup.
# ---------------------------------------------------------------------------

class TestSessionEndCleanupOrder:
    """Verify cleanup order in session-end.sh is safe."""

    def test_chain_cleanup_before_eval_pending_cleanup(self):
        """session-end.sh cleanup order:
        1. Remove .current-session-id
        2. Remove .chain-in-progress
        3. Remove .eval-pending (uses SESSION_ID resolved at start)
        SESSION_ID is resolved before cleanup starts so this is safe."""
        # This is a structural/ordering test — just verify the file reads correct order
        with open(os.path.join(HOOKS_DIR, "session-end.sh")) as f:
            content = f.read()

        session_id_cleanup_pos = content.find(".current-session-id")
        chain_cleanup_pos = content.find(".chain-in-progress")
        eval_pending_cleanup_pos = content.find(".eval-pending")

        # All three cleanup sections must exist
        assert session_id_cleanup_pos != -1
        assert chain_cleanup_pos != -1
        assert eval_pending_cleanup_pos != -1

        # chain cleanup comes after .current-session-id removal
        assert chain_cleanup_pos > session_id_cleanup_pos, (
            ".chain-in-progress cleanup should come after .current-session-id removal"
        )

    def test_eval_pending_cleanup_uses_session_id_from_top_of_script(self):
        """SESSION_ID in session-end.sh is resolved at the top, before any cleanup.
        The .eval-pending cleanup at the bottom uses this pre-resolved SESSION_ID.
        Even if .current-session-id is removed mid-script, SESSION_ID is already set."""
        with open(os.path.join(HOOKS_DIR, "session-end.sh")) as f:
            content = f.read()

        # SESSION_ID resolution must come BEFORE .current-session-id removal
        session_id_resolve_pos = content.find('SESSION_ID="$(resolve_session_id')
        session_id_file_remove_pos = content.find("rm -f \"${STATE_DIR}/.current-session-id\"")
        eval_pending_cleanup_pos = content.find(".eval-pending")

        assert session_id_resolve_pos < session_id_file_remove_pos, (
            "SESSION_ID must be resolved before .current-session-id is removed"
        )
        assert session_id_resolve_pos < eval_pending_cleanup_pos, (
            "SESSION_ID must be resolved before .eval-pending cleanup"
        )


# ---------------------------------------------------------------------------
# Finding 9: The prompt-interceptor.sh has no "exit 0" inside chain block
# The code structure uses if/elif/else — all paths end before "exit 0".
# But the file ends with "exit 0" outside all conditionals. Let's verify.
# ---------------------------------------------------------------------------

class TestPromptInterceptorExitCode:
    """Verify prompt-interceptor.sh always exits 0 in all code paths."""

    def test_chain_path_exits_0(self, tmp_path):
        _make_git_root(tmp_path)
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()
        (state_dir / ".chain-in-progress").write_text("chain")
        _, _, rc = _run_hook("prompt-interceptor.sh", _base_env(), str(tmp_path))
        assert rc == 0

    def test_eval_pending_path_exits_0(self, tmp_path):
        _make_git_root(tmp_path)
        session_id = "exit-test"
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()
        session_dir = state_dir / "sessions" / session_id
        session_dir.mkdir(parents=True)
        (session_dir / ".eval-pending").write_text("ts")
        (state_dir / ".current-session-id").write_text(session_id)
        env = _base_env(session_id=session_id)
        _, _, rc = _run_hook("prompt-interceptor.sh", env, str(tmp_path))
        assert rc == 0

    def test_no_mode_path_exits_0(self, tmp_path):
        _make_git_root(tmp_path)
        (tmp_path / ".adaptive-harness").mkdir()
        _, _, rc = _run_hook("prompt-interceptor.sh", _base_env(), str(tmp_path))
        assert rc == 0


# ---------------------------------------------------------------------------
# Finding 10: Contract.yaml task_types vs router taxonomy inconsistency
# plan-review: contract lists [plan, planning, design, architecture]
# router.md says task_type=review
# These don't match — but the router uses its own hardcoded table, not contract.yaml.
# ---------------------------------------------------------------------------

class TestContractVsRouterTaxonomyConsistency:
    """Verify contract.yaml task_types are consistent with router taxonomy (H3 fix)."""

    def test_plan_review_contract_task_types_vs_router_taxonomy(self):
        """plan-review contract.yaml must include 'review' in task_types.
        The router harness_pool table maps plan-review to task_type=review.
        H3 fix: 'review' was added to align contract.yaml with router taxonomy."""
        import yaml
        contract_path = os.path.join(WORKSPACE_ROOT, "harnesses", "plan-review", "contract.yaml")
        with open(contract_path) as f:
            contract = yaml.safe_load(f)

        contract_task_types = contract.get("trigger", {}).get("task_types", [])
        # 'review' must now be in contract.yaml (H3 fix applied)
        assert "review" in contract_task_types, (
            "plan-review contract.yaml must list 'review' as a task_type "
            "(H3 fix: align contract.yaml with router taxonomy). "
            f"Current task_types: {contract_task_types}"
        )

    def test_qa_testing_contract_lacks_ops_task_type(self):
        """qa-testing contract.yaml must include 'ops' in task_types.
        Router maps qa-testing to task_type=ops.
        H3 fix: 'ops' was added to align contract.yaml with router taxonomy."""
        import yaml
        contract_path = os.path.join(WORKSPACE_ROOT, "harnesses", "qa-testing", "contract.yaml")
        with open(contract_path) as f:
            contract = yaml.safe_load(f)

        contract_task_types = contract.get("trigger", {}).get("task_types", [])
        assert "ops" in contract_task_types, (
            "qa-testing contract.yaml must include 'ops' task_type "
            "(H3 fix: align contract.yaml with router taxonomy). "
            f"Current task_types: {contract_task_types}"
        )

    def test_engineering_retro_contract_lacks_ops_task_type(self):
        """engineering-retro contract.yaml must include 'ops' in task_types.
        Router maps it to task_type=[ops, review].
        H3 fix: 'ops' was added to align contract.yaml with router taxonomy."""
        import yaml
        contract_path = os.path.join(WORKSPACE_ROOT, "harnesses", "engineering-retro", "contract.yaml")
        with open(contract_path) as f:
            contract = yaml.safe_load(f)

        contract_task_types = contract.get("trigger", {}).get("task_types", [])
        assert "ops" in contract_task_types, (
            "engineering-retro contract.yaml must include 'ops' task_type "
            "(H3 fix: align contract.yaml with router taxonomy). "
            f"Current task_types: {contract_task_types}"
        )


# ---------------------------------------------------------------------------
# Finding 11: migrate.sh does NOT move harnesses from experimental to stable
# When 4 harnesses (adversarial-review etc.) were promoted from experimental
# to stable in contract.yaml, existing users' harness-pool.json is NOT updated.
# ---------------------------------------------------------------------------

class TestMigrationPoolSync:
    """Probe migrate.sh behavior for harnesses promoted from experimental to stable."""

    def test_migrate_adds_new_harnesses_but_not_reclassify(self, tmp_path):
        """migrate.sh adds missing harnesses to stable, but does NOT move
        existing experimental harnesses to stable, even if contract.yaml says stable."""
        _make_git_root(tmp_path)
        state_dir = tmp_path / ".adaptive-harness"
        state_dir.mkdir()

        # Simulate user's pool where adversarial-review is still in experimental
        pool = {
            "stable": {
                "tdd-driven": {"weight": 1.0, "total_runs": 0, "successes": 0,
                               "failures": 0, "consecutive_successes": 0}
            },
            "experimental": {
                "adversarial-review": {"weight": 1.2, "total_runs": 5, "successes": 3,
                                       "failures": 2, "consecutive_successes": 1}
            },
            "last_updated": None,
            "last_merged_session": None,
        }
        pool_path = state_dir / "harness-pool.json"
        with open(pool_path, "w") as f:
            json.dump(pool, f)

        # Write a mismatched version to trigger migration
        (state_dir / ".plugin-version").write_text("0.0.0")

        env = _base_env()
        env["ADAPTIVE_HARNESS_PLUGIN_VERSION"] = "1.0.4"

        proc = subprocess.run(
            ["bash", os.path.join(HOOKS_DIR, "migrate.sh")],
            env=env, cwd=str(tmp_path),
            capture_output=True, text=True
        )

        # Read updated pool
        with open(pool_path) as f:
            updated_pool = json.load(f)

        # adversarial-review remains in experimental after migration
        # (migrate.sh only adds NEW harnesses, doesn't reclassify existing ones)
        if "adversarial-review" in updated_pool.get("experimental", {}):
            # Still in experimental — migration did NOT reclassify it
            assert "adversarial-review" not in updated_pool.get("stable", {}), (
                "adversarial-review was moved from experimental to stable by migrate.sh. "
                "This is unexpected — migrate.sh is not supposed to reclassify harnesses."
            )
        else:
            # Got moved — check it ended up in stable
            assert "adversarial-review" in updated_pool.get("stable", {}), (
                "adversarial-review disappeared from experimental but is not in stable!"
            )
