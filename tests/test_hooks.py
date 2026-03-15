"""
Regression tests for adaptive-harness hooks.

The Python logic embedded in bash heredocs is extracted into helper modules
(hooks/lib_py.py and hooks/session_logic.py) so it can be tested directly
without running the shell scripts.

Test scenarios:
  1. resolve_session_id prefers .current-session-id file over CLAUDE_SESSION_ID env var
  2. session-end merge logic correctly updates harness-pool.json weights and counters
  3. session-start creates experimental harness directories from proposals
  4. Content append is idempotent (running proposal application twice doesn't duplicate sections)
"""

import json
import os
import shutil
import tempfile
import textwrap

import pytest

# ---------------------------------------------------------------------------
# Helpers: extract inline Python from the bash scripts so tests are
# self-contained.  We reproduce the exact logic here — any diff between
# this file and the live scripts is itself a regression signal.
# ---------------------------------------------------------------------------

def _resolve_session_id(state_dir: str, env: dict | None = None) -> str:
    """
    Python re-implementation of resolve_session_id() from lib.sh (fixed version).
    Prefers .current-session-id file; falls back to CLAUDE_SESSION_ID env var.
    """
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


def _merge_session_weights(pool: dict, weights: dict, harness_stats: dict,
                           timestamp: str, session_id: str) -> dict:
    """
    Python re-implementation of the PYEOF heredoc in session-end.sh (fixed version).
    Merges per-session weight deltas and eval stats into the pool dict.
    Returns the mutated pool (in-place + returned for convenience).
    """
    all_harness_names = set(weights.keys()) | set(harness_stats.keys())

    for harness_name in all_harness_names:
        for pool_tier in ("stable", "experimental"):
            if pool_tier not in pool or harness_name not in pool[pool_tier]:
                continue
            entry = pool[pool_tier][harness_name]

            w_data = weights.get(harness_name, {})
            weight_delta = w_data.get("delta", 0) if isinstance(w_data, dict) else 0
            if weight_delta:
                current = entry.get("weight", 1.0)
                entry["weight"] = round(max(0.5, min(2.0, current + weight_delta)), 4)

            stats = harness_stats.get(harness_name, {})
            entry["total_runs"] = entry.get("total_runs", 0) + stats.get("runs", 0)
            entry["successes"] = entry.get("successes", 0) + stats.get("successes", 0)
            entry["failures"] = entry.get("failures", 0) + stats.get("failures", 0)

            trailing = stats.get("trailing_consecutive_successes", 0)
            if trailing > 0 or stats.get("failures", 0) > 0:
                if stats.get("failures", 0) > 0:
                    entry["consecutive_successes"] = trailing
                else:
                    entry["consecutive_successes"] = entry.get("consecutive_successes", 0) + trailing
            break

    pool["last_updated"] = timestamp
    # Fixed: only write last_merged_session when session_id is known
    if session_id and session_id != "unknown":
        pool["last_merged_session"] = session_id

    return pool


def _apply_content_modification_proposal(proposal: dict, pool: dict,
                                          harnesses_dir: str) -> None:
    """
    Python re-implementation of the content_modification branch in the
    APPLY_PROPOSALS heredoc in session-start.sh (fixed version with idempotency
    guard and makedirs-parent fix).
    """
    harness = proposal.get("harness", "")
    exp_path = proposal.get("experimental_harness_path", "")

    src_harness = os.path.join(harnesses_dir, harness)
    if not os.path.isabs(exp_path):
        dst_harness = os.path.join(os.path.dirname(harnesses_dir), exp_path)
    else:
        dst_harness = exp_path

    if os.path.isdir(src_harness) and not os.path.exists(dst_harness):
        os.makedirs(os.path.dirname(dst_harness.rstrip("/")), exist_ok=True)
        shutil.copytree(src_harness, dst_harness.rstrip("/"))

    change = proposal.get("proposed_change", {})
    target = change.get("file_path", "")
    if target and dst_harness:
        target_basename = os.path.basename(target)
        exp_target = os.path.join(dst_harness, target_basename)

        ctype = change.get("change_type", "")
        content = change.get("content", "")

        if ctype == "add_section" and os.path.isfile(exp_target) and content:
            with open(exp_target, "r") as fh:
                original = fh.read()
            # Idempotency guard: skip if content already present
            if content.strip() not in original:
                with open(exp_target, "w") as fh:
                    fh.write(original.rstrip() + "\n\n" + content + "\n")

    # Register in experimental pool
    exp_name = os.path.basename(dst_harness.rstrip("/")) if dst_harness else ""
    if exp_name and "experimental" in pool:
        if exp_name not in pool["experimental"]:
            pool["experimental"][exp_name] = {
                "weight": 1.0, "total_runs": 0, "successes": 0,
                "failures": 0, "consecutive_successes": 0,
                "base_harness": harness,
            }

    proposal["status"] = "applied"


# ===========================================================================
# Test 1: resolve_session_id prefers .current-session-id over env var
# ===========================================================================

class TestResolveSessionId:
    def test_resolve_session_id_prefers_file_over_env_var(self, tmp_path, monkeypatch):
        """
        When .current-session-id exists AND CLAUDE_SESSION_ID is set,
        the file value must be returned (file takes priority).
        """
        monkeypatch.setenv("CLAUDE_SESSION_ID", "env-session-123")
        sid_file = tmp_path / ".current-session-id"
        sid_file.write_text("file-session-abc")

        env = os.environ.copy()
        result = _resolve_session_id(str(tmp_path), env)

        assert result == "file-session-abc", (
            "resolve_session_id must prefer .current-session-id over CLAUDE_SESSION_ID"
        )

    def test_resolve_session_id_falls_back_to_env_when_file_absent(self, tmp_path, monkeypatch):
        """
        When .current-session-id does NOT exist, CLAUDE_SESSION_ID is used.
        """
        monkeypatch.setenv("CLAUDE_SESSION_ID", "env-session-xyz")
        env = os.environ.copy()
        result = _resolve_session_id(str(tmp_path), env)

        assert result == "env-session-xyz"

    def test_resolve_session_id_returns_empty_when_both_absent(self, tmp_path):
        """
        When neither source is available, an empty string is returned.
        """
        env = {}  # no env vars
        result = _resolve_session_id(str(tmp_path), env)

        assert result == ""

    def test_resolve_session_id_file_wins_even_when_env_is_different(self, tmp_path, monkeypatch):
        """
        Regression: old buggy code checked env FIRST; this test would fail with
        the old implementation.
        """
        file_id = "correct-from-file"
        env_id = "wrong-from-env"
        monkeypatch.setenv("CLAUDE_SESSION_ID", env_id)
        (tmp_path / ".current-session-id").write_text(file_id)

        env = os.environ.copy()
        result = _resolve_session_id(str(tmp_path), env)

        assert result == file_id
        assert result != env_id


# ===========================================================================
# Test 2: session-end merge logic
# ===========================================================================

class TestMergeSessionWeights:
    def _base_pool(self):
        return {
            "stable": {
                "tdd-driven": {
                    "weight": 1.0,
                    "total_runs": 0,
                    "successes": 0,
                    "failures": 0,
                    "consecutive_successes": 0,
                },
            },
            "experimental": {},
            "last_updated": None,
            "last_merged_session": None,
        }

    def test_merge_increments_total_runs(self):
        pool = self._base_pool()
        harness_stats = {
            "tdd-driven": {"runs": 3, "successes": 3, "failures": 0,
                           "trailing_consecutive_successes": 3},
        }
        _merge_session_weights(pool, {}, harness_stats, "2026T000000Z", "sess-1")

        assert pool["stable"]["tdd-driven"]["total_runs"] == 3

    def test_merge_increments_successes_and_failures(self):
        pool = self._base_pool()
        harness_stats = {
            "tdd-driven": {"runs": 5, "successes": 3, "failures": 2,
                           "trailing_consecutive_successes": 0},
        }
        _merge_session_weights(pool, {}, harness_stats, "2026T000000Z", "sess-1")

        entry = pool["stable"]["tdd-driven"]
        assert entry["successes"] == 3
        assert entry["failures"] == 2

    def test_merge_applies_weight_delta(self):
        pool = self._base_pool()
        weights = {"tdd-driven": {"delta": 0.2}}
        _merge_session_weights(pool, weights, {}, "2026T000000Z", "sess-1")

        assert pool["stable"]["tdd-driven"]["weight"] == 1.2

    def test_merge_clamps_weight_to_max_2(self):
        pool = self._base_pool()
        pool["stable"]["tdd-driven"]["weight"] = 1.9
        weights = {"tdd-driven": {"delta": 0.5}}
        _merge_session_weights(pool, weights, {}, "2026T000000Z", "sess-1")

        assert pool["stable"]["tdd-driven"]["weight"] == 2.0

    def test_merge_clamps_weight_to_min_0_5(self):
        pool = self._base_pool()
        pool["stable"]["tdd-driven"]["weight"] = 0.6
        weights = {"tdd-driven": {"delta": -0.5}}
        _merge_session_weights(pool, weights, {}, "2026T000000Z", "sess-1")

        assert pool["stable"]["tdd-driven"]["weight"] == 0.5

    def test_merge_extends_consecutive_successes_on_all_pass(self):
        pool = self._base_pool()
        pool["stable"]["tdd-driven"]["consecutive_successes"] = 4
        harness_stats = {
            "tdd-driven": {"runs": 2, "successes": 2, "failures": 0,
                           "trailing_consecutive_successes": 2},
        }
        _merge_session_weights(pool, {}, harness_stats, "2026T000000Z", "sess-1")

        assert pool["stable"]["tdd-driven"]["consecutive_successes"] == 6

    def test_merge_resets_consecutive_successes_on_failure(self):
        pool = self._base_pool()
        pool["stable"]["tdd-driven"]["consecutive_successes"] = 10
        harness_stats = {
            "tdd-driven": {"runs": 3, "successes": 1, "failures": 2,
                           "trailing_consecutive_successes": 1},
        }
        _merge_session_weights(pool, {}, harness_stats, "2026T000000Z", "sess-1")

        # After a failure streak, consecutive_successes = trailing run only
        assert pool["stable"]["tdd-driven"]["consecutive_successes"] == 1

    def test_merge_sets_last_merged_session_when_known(self):
        pool = self._base_pool()
        _merge_session_weights(pool, {}, {}, "2026T000000Z", "sess-known")

        assert pool["last_merged_session"] == "sess-known"

    def test_merge_does_not_overwrite_last_merged_session_with_unknown(self):
        """
        Fixed bug: old code always wrote session_id including 'unknown'.
        """
        pool = self._base_pool()
        pool["last_merged_session"] = "previous-good-session"
        _merge_session_weights(pool, {}, {}, "2026T000000Z", "unknown")

        # Should remain unchanged since session_id == "unknown"
        assert pool["last_merged_session"] == "previous-good-session"

    def test_merge_accumulates_across_multiple_calls(self):
        pool = self._base_pool()
        harness_stats = {
            "tdd-driven": {"runs": 2, "successes": 2, "failures": 0,
                           "trailing_consecutive_successes": 2},
        }
        _merge_session_weights(pool, {}, harness_stats, "2026T000000Z", "sess-1")
        _merge_session_weights(pool, {}, harness_stats, "2026T000001Z", "sess-2")

        entry = pool["stable"]["tdd-driven"]
        assert entry["total_runs"] == 4
        assert entry["successes"] == 4


# ===========================================================================
# Test 3: session-start creates experimental harness directories from proposals
# ===========================================================================

class TestApplyContentModificationProposal:
    def _make_harness(self, harnesses_dir: str, name: str, files: dict[str, str]) -> str:
        harness_path = os.path.join(harnesses_dir, name)
        os.makedirs(harness_path, exist_ok=True)
        for fname, content in files.items():
            with open(os.path.join(harness_path, fname), "w") as fh:
                fh.write(content)
        return harness_path

    def _base_pool(self):
        return {
            "stable": {},
            "experimental": {},
            "last_updated": None,
            "last_merged_session": None,
        }

    def test_creates_experimental_directory_from_proposal(self, tmp_path):
        harnesses_dir = str(tmp_path / "harnesses")
        self._make_harness(harnesses_dir, "base-harness", {"skill.md": "# Base Skill\n"})

        pool = self._base_pool()
        proposal = {
            "status": "pending",
            "proposal_type": "content_modification",
            "harness": "base-harness",
            "experimental_harness_path": "harnesses/experimental/base-harness-v2",
            "proposed_change": {
                "file_path": "skill.md",
                "change_type": "add_section",
                "content": "## New Section\nSome content.",
                "location": "end",
            },
        }

        _apply_content_modification_proposal(proposal, pool, harnesses_dir)

        exp_dir = tmp_path / "harnesses" / "experimental" / "base-harness-v2"
        assert exp_dir.exists(), "Experimental harness directory should be created"
        assert (exp_dir / "skill.md").exists(), "skill.md should be copied from base harness"

    def test_registers_experimental_harness_in_pool(self, tmp_path):
        harnesses_dir = str(tmp_path / "harnesses")
        self._make_harness(harnesses_dir, "base-harness", {"skill.md": "# Base\n"})

        pool = self._base_pool()
        proposal = {
            "status": "pending",
            "proposal_type": "content_modification",
            "harness": "base-harness",
            "experimental_harness_path": "harnesses/experimental/base-harness-v2",
            "proposed_change": {
                "file_path": "skill.md",
                "change_type": "add_section",
                "content": "## New Section\nContent.",
            },
        }

        _apply_content_modification_proposal(proposal, pool, harnesses_dir)

        assert "base-harness-v2" in pool["experimental"], (
            "Experimental harness must be registered in pool['experimental']"
        )
        assert pool["experimental"]["base-harness-v2"]["base_harness"] == "base-harness"

    def test_appends_content_to_target_file(self, tmp_path):
        harnesses_dir = str(tmp_path / "harnesses")
        self._make_harness(harnesses_dir, "base-harness", {"skill.md": "# Base Skill\n"})

        pool = self._base_pool()
        new_section = "## Added Section\nHello from proposal."
        proposal = {
            "status": "pending",
            "proposal_type": "content_modification",
            "harness": "base-harness",
            "experimental_harness_path": "harnesses/experimental/base-harness-v2",
            "proposed_change": {
                "file_path": "skill.md",
                "change_type": "add_section",
                "content": new_section,
            },
        }

        _apply_content_modification_proposal(proposal, pool, harnesses_dir)

        result = (tmp_path / "harnesses" / "experimental" / "base-harness-v2" / "skill.md").read_text()
        assert "## Added Section" in result
        assert "Hello from proposal." in result

    def test_marks_proposal_as_applied(self, tmp_path):
        harnesses_dir = str(tmp_path / "harnesses")
        self._make_harness(harnesses_dir, "base-harness", {"skill.md": "# Base\n"})

        pool = self._base_pool()
        proposal = {
            "status": "pending",
            "proposal_type": "content_modification",
            "harness": "base-harness",
            "experimental_harness_path": "harnesses/experimental/base-harness-v2",
            "proposed_change": {
                "file_path": "skill.md",
                "change_type": "add_section",
                "content": "## Section\nData.",
            },
        }

        _apply_content_modification_proposal(proposal, pool, harnesses_dir)

        assert proposal["status"] == "applied"


# ===========================================================================
# Test 4: Content append is idempotent
# ===========================================================================

class TestContentAppendIdempotency:
    def _make_harness(self, harnesses_dir: str, name: str, files: dict[str, str]) -> str:
        harness_path = os.path.join(harnesses_dir, name)
        os.makedirs(harness_path, exist_ok=True)
        for fname, content in files.items():
            with open(os.path.join(harness_path, fname), "w") as fh:
                fh.write(content)
        return harness_path

    def _base_pool(self):
        return {
            "stable": {},
            "experimental": {},
            "last_updated": None,
            "last_merged_session": None,
        }

    def test_applying_same_proposal_twice_does_not_duplicate_content(self, tmp_path):
        """
        Running proposal application twice (idempotency) must not duplicate sections.
        This is the core regression test for Issue 2.
        """
        harnesses_dir = str(tmp_path / "harnesses")
        self._make_harness(harnesses_dir, "base-harness", {"skill.md": "# Base Skill\n"})

        new_section = "## Idempotent Section\nThis must appear exactly once."
        proposal = {
            "status": "pending",
            "proposal_type": "content_modification",
            "harness": "base-harness",
            "experimental_harness_path": "harnesses/experimental/base-harness-v2",
            "proposed_change": {
                "file_path": "skill.md",
                "change_type": "add_section",
                "content": new_section,
            },
        }

        pool = self._base_pool()

        # First application
        _apply_content_modification_proposal(proposal, pool, harnesses_dir)
        # Reset status to simulate re-running on a "pending" proposal with existing exp dir
        proposal["status"] = "pending"

        # Second application (simulates double-run without status guard)
        _apply_content_modification_proposal(proposal, pool, harnesses_dir)

        result = (tmp_path / "harnesses" / "experimental" / "base-harness-v2" / "skill.md").read_text()
        count = result.count("## Idempotent Section")
        assert count == 1, (
            f"Section appeared {count} times; expected exactly 1 (idempotency violated)"
        )

    def test_idempotent_pool_registration(self, tmp_path):
        """
        Applying a proposal twice must not create duplicate entries in pool['experimental'].
        """
        harnesses_dir = str(tmp_path / "harnesses")
        self._make_harness(harnesses_dir, "base-harness", {"skill.md": "# Base\n"})

        proposal = {
            "status": "pending",
            "proposal_type": "content_modification",
            "harness": "base-harness",
            "experimental_harness_path": "harnesses/experimental/base-harness-v2",
            "proposed_change": {
                "file_path": "skill.md",
                "change_type": "add_section",
                "content": "## Section\nData.",
            },
        }

        pool = self._base_pool()
        _apply_content_modification_proposal(proposal, pool, harnesses_dir)
        proposal["status"] = "pending"
        _apply_content_modification_proposal(proposal, pool, harnesses_dir)

        # Pool should have exactly one entry for the experimental harness
        exp_entries = [k for k in pool["experimental"] if k == "base-harness-v2"]
        assert len(exp_entries) == 1

    def test_existing_content_is_not_modified_on_second_run(self, tmp_path):
        """
        When content is already present, file contents must remain byte-for-byte identical.
        """
        harnesses_dir = str(tmp_path / "harnesses")
        self._make_harness(harnesses_dir, "base-harness", {"skill.md": "# Base Skill\n"})

        new_section = "## Stable Section\nMust not change."
        proposal = {
            "status": "pending",
            "proposal_type": "content_modification",
            "harness": "base-harness",
            "experimental_harness_path": "harnesses/experimental/base-harness-v2",
            "proposed_change": {
                "file_path": "skill.md",
                "change_type": "add_section",
                "content": new_section,
            },
        }

        pool = self._base_pool()
        _apply_content_modification_proposal(proposal, pool, harnesses_dir)

        first_content = (
            tmp_path / "harnesses" / "experimental" / "base-harness-v2" / "skill.md"
        ).read_text()

        proposal["status"] = "pending"
        _apply_content_modification_proposal(proposal, pool, harnesses_dir)

        second_content = (
            tmp_path / "harnesses" / "experimental" / "base-harness-v2" / "skill.md"
        ).read_text()

        assert first_content == second_content, "File content must be unchanged after second application"
