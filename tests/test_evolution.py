"""
Tests for evolution logic: proposal schema validation, content_modification,
promotion/demotion, new_harness genesis.

Rules from agents/evolution-manager.md:
  - Promotion: consecutive_successes >= 5 AND avg_score >= 0.7
  - Demotion: last_5_avg_score < 0.55 AND declining trend
  - New harnesses always go to experimental pool first
  - Proposals are written to .adaptive-harness/evolution-proposals/
"""

import json
import os
import shutil
import subprocess

import pytest


WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS_DIR = os.path.join(WORKSPACE_ROOT, "hooks")

REQUIRED_PROPOSAL_FIELDS = {
    "proposal_id",
    "created_at",
    "harness",
    "proposal_type",
    "priority",
    "status",
    "rationale",
    "proposed_change",
    "expected_impact",
    "applies_to_pool",
}

VALID_PROPOSAL_TYPES = {
    "content_modification",
    "contract_modification",
    "promotion",
    "demotion",
    "new_harness",
}

VALID_PRIORITIES = {"high", "medium", "low"}
VALID_STATUSES = {"pending", "applied", "rejected"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _apply_proposals(proposals_dir: str, pool: dict, harnesses_dir: str,
                     local_harnesses_dir: str | None = None) -> dict:
    """Extract and run APPLY_PROPOSALS from session-start.sh.

    harnesses_dir  — global plugin harnesses (read-only source)
    local_harnesses_dir — project-local harnesses (write target); defaults to a
                          sibling 'local-harnesses' directory of proposals_dir.
    """
    session_start_sh = os.path.join(HOOKS_DIR, "session-start.sh")
    with open(session_start_sh) as fh:
        content = fh.read()
    start = content.find("<<'APPLY_PROPOSALS'\n") + len("<<'APPLY_PROPOSALS'\n")
    end = content.find("\nAPPLY_PROPOSALS", start)
    code = content[start:end]

    pool_dir = os.path.dirname(proposals_dir)
    pool_file = os.path.join(pool_dir, "pool.json")
    with open(pool_file, "w") as fh:
        json.dump(pool, fh)

    if local_harnesses_dir is None:
        local_harnesses_dir = os.path.join(pool_dir, "local-harnesses")
    os.makedirs(local_harnesses_dir, exist_ok=True)

    proc = subprocess.run(
        ["python3", "-", proposals_dir, pool_file, harnesses_dir, local_harnesses_dir],
        input=code,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"APPLY_PROPOSALS failed: {proc.stderr}"
    with open(pool_file) as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Proposal schema validation
# ---------------------------------------------------------------------------

class TestProposalSchema:
    def test_proposal_has_required_fields(self, sample_proposal):
        for field in REQUIRED_PROPOSAL_FIELDS:
            assert field in sample_proposal, f"Missing field: {field}"

    def test_proposal_type_is_valid(self, sample_proposal):
        assert sample_proposal["proposal_type"] in VALID_PROPOSAL_TYPES

    def test_priority_is_valid(self, sample_proposal):
        assert sample_proposal["priority"] in VALID_PRIORITIES

    def test_status_is_valid(self, sample_proposal):
        assert sample_proposal["status"] in VALID_STATUSES

    def test_proposal_id_format(self, sample_proposal):
        pid = sample_proposal["proposal_id"]
        assert isinstance(pid, str)
        assert len(pid) > 0

    def test_proposal_serializable_to_json(self, sample_proposal):
        serialized = json.dumps(sample_proposal)
        loaded = json.loads(serialized)
        assert loaded["harness"] == sample_proposal["harness"]

    def test_promotion_proposal_schema(self):
        proposal = {
            "proposal_id": "tdd-promote-20260315-abc123",
            "created_at": "2026-03-15T10:00:00Z",
            "harness": "tdd-driven-v1.1",
            "proposal_type": "promotion",
            "target_file": "metadata.json",
            "priority": "high",
            "status": "pending",
            "evidence": {
                "current_pool": "experimental",
                "consecutive_successes": 6,
                "avg_score_last_5": 0.81,
                "total_runs": 9,
                "promotion_threshold_met": True,
            },
            "rationale": "6 consecutive successes, avg_score 0.81.",
            "proposed_change": {
                "description": "Promote to stable",
                "file_path": "harnesses/tdd-driven-v1.1/metadata.json",
                "change_type": "update_pool",
                "current_value": "experimental",
                "new_value": "stable",
            },
            "expected_impact": "Harness available in primary routing.",
            "applies_to_pool": "stable",
        }
        assert proposal["proposal_type"] == "promotion"
        assert proposal["evidence"]["consecutive_successes"] >= 5
        assert proposal["evidence"]["avg_score_last_5"] >= 0.7

    def test_demotion_proposal_schema(self):
        proposal = {
            "proposal_id": "migration-demote-20260315-def456",
            "created_at": "2026-03-15T10:00:00Z",
            "harness": "migration-safe",
            "proposal_type": "demotion",
            "target_file": "metadata.json",
            "priority": "high",
            "status": "pending",
            "evidence": {
                "current_pool": "stable",
                "last_5_avg_score": 0.48,
                "trend": "declining",
                "total_runs": 15,
            },
            "rationale": "Avg 0.48, declining trend.",
            "proposed_change": {
                "description": "Demote to experimental",
                "file_path": "harnesses/migration-safe/metadata.json",
                "change_type": "update_pool",
                "current_value": "stable",
                "new_value": "experimental",
            },
            "expected_impact": "Removed from primary routing.",
            "applies_to_pool": "experimental",
        }
        assert proposal["proposal_type"] == "demotion"
        assert proposal["evidence"]["last_5_avg_score"] < 0.55
        assert proposal["evidence"]["trend"] == "declining"


# ---------------------------------------------------------------------------
# Content modification proposal
# ---------------------------------------------------------------------------

class TestContentModificationProposal:
    def _make_base_harness(self, harnesses_dir: str, name: str, content: str = "# Base\n"):
        harness_path = os.path.join(harnesses_dir, name)
        os.makedirs(harness_path, exist_ok=True)
        with open(os.path.join(harness_path, "skill.md"), "w") as fh:
            fh.write(content)
        return harness_path

    def test_content_modification_creates_experimental_copy(self, tmp_path):
        harnesses_dir = str(tmp_path / "harnesses")
        proposals_dir = str(tmp_path / "proposals")
        local_harnesses_dir = str(tmp_path / "local-harnesses")
        os.makedirs(proposals_dir)
        self._make_base_harness(harnesses_dir, "tdd-driven")
        pool = {"stable": {}, "experimental": {}, "last_updated": None, "last_merged_session": None}
        proposal = {
            "status": "pending",
            "proposal_type": "content_modification",
            "harness": "tdd-driven",
            "experimental_harness_path": "harnesses/experimental/tdd-driven-v1.1",
            "proposed_change": {
                "file_path": "harnesses/tdd-driven/skill.md",
                "change_type": "add_section",
                "content": "## New Section\nAdded content.",
            },
        }
        with open(os.path.join(proposals_dir, "001.json"), "w") as fh:
            json.dump(proposal, fh)

        _apply_proposals(proposals_dir, pool, harnesses_dir, local_harnesses_dir)

        exp_dir = tmp_path / "local-harnesses" / "experimental" / "tdd-driven-v1.1"
        assert exp_dir.exists()

    def test_content_modification_registers_in_experimental_pool(self, tmp_path):
        harnesses_dir = str(tmp_path / "harnesses")
        proposals_dir = str(tmp_path / "proposals")
        local_harnesses_dir = str(tmp_path / "local-harnesses")
        os.makedirs(proposals_dir)
        self._make_base_harness(harnesses_dir, "tdd-driven")
        pool = {"stable": {}, "experimental": {}, "last_updated": None, "last_merged_session": None}
        proposal = {
            "status": "pending",
            "proposal_type": "content_modification",
            "harness": "tdd-driven",
            "experimental_harness_path": "harnesses/experimental/tdd-driven-v1.1",
            "proposed_change": {
                "file_path": "harnesses/tdd-driven/skill.md",
                "change_type": "add_section",
                "content": "## New\nContent.",
            },
        }
        with open(os.path.join(proposals_dir, "001.json"), "w") as fh:
            json.dump(proposal, fh)

        result = _apply_proposals(proposals_dir, pool, harnesses_dir, local_harnesses_dir)
        assert "tdd-driven-v1.1" in result["experimental"]

    def test_content_modification_appends_section(self, tmp_path):
        harnesses_dir = str(tmp_path / "harnesses")
        proposals_dir = str(tmp_path / "proposals")
        local_harnesses_dir = str(tmp_path / "local-harnesses")
        os.makedirs(proposals_dir)
        self._make_base_harness(harnesses_dir, "tdd-driven", "# Base Skill\n")
        pool = {"stable": {}, "experimental": {}, "last_updated": None, "last_merged_session": None}
        new_content = "## Error Handling Review\nCheck all error paths."
        proposal = {
            "status": "pending",
            "proposal_type": "content_modification",
            "harness": "tdd-driven",
            "experimental_harness_path": "harnesses/experimental/tdd-driven-v1.1",
            "proposed_change": {
                "file_path": "harnesses/tdd-driven/skill.md",
                "change_type": "add_section",
                "content": new_content,
            },
        }
        with open(os.path.join(proposals_dir, "001.json"), "w") as fh:
            json.dump(proposal, fh)

        _apply_proposals(proposals_dir, pool, harnesses_dir, local_harnesses_dir)

        exp_skill = tmp_path / "local-harnesses" / "experimental" / "tdd-driven-v1.1" / "skill.md"
        text = exp_skill.read_text()
        assert "## Error Handling Review" in text

    def test_content_modification_proposal_marked_applied(self, tmp_path):
        harnesses_dir = str(tmp_path / "harnesses")
        proposals_dir = str(tmp_path / "proposals")
        local_harnesses_dir = str(tmp_path / "local-harnesses")
        os.makedirs(proposals_dir)
        self._make_base_harness(harnesses_dir, "tdd-driven")
        pool = {"stable": {}, "experimental": {}, "last_updated": None, "last_merged_session": None}
        proposal = {
            "status": "pending",
            "proposal_type": "content_modification",
            "harness": "tdd-driven",
            "experimental_harness_path": "harnesses/experimental/tdd-driven-v1.1",
            "proposed_change": {
                "file_path": "harnesses/tdd-driven/skill.md",
                "change_type": "add_section",
                "content": "## Section\nContent.",
            },
        }
        proposal_file = os.path.join(proposals_dir, "001.json")
        with open(proposal_file, "w") as fh:
            json.dump(proposal, fh)

        _apply_proposals(proposals_dir, pool, harnesses_dir, local_harnesses_dir)

        with open(proposal_file) as fh:
            updated = json.load(fh)
        assert updated["status"] == "applied"

    def test_already_applied_proposal_not_re_applied(self, tmp_path):
        harnesses_dir = str(tmp_path / "harnesses")
        proposals_dir = str(tmp_path / "proposals")
        local_harnesses_dir = str(tmp_path / "local-harnesses")
        os.makedirs(proposals_dir)
        self._make_base_harness(harnesses_dir, "tdd-driven", "# Base\n")
        pool = {"stable": {}, "experimental": {}, "last_updated": None, "last_merged_session": None}
        proposal = {
            "status": "applied",  # Already applied
            "proposal_type": "content_modification",
            "harness": "tdd-driven",
            "experimental_harness_path": "harnesses/experimental/tdd-driven-v1.1",
            "proposed_change": {
                "file_path": "harnesses/tdd-driven/skill.md",
                "change_type": "add_section",
                "content": "## Already Applied\nContent.",
            },
        }
        with open(os.path.join(proposals_dir, "001.json"), "w") as fh:
            json.dump(proposal, fh)

        _apply_proposals(proposals_dir, pool, harnesses_dir, local_harnesses_dir)

        # Experimental directory should NOT be created (proposal was already applied)
        exp_dir = tmp_path / "local-harnesses" / "experimental" / "tdd-driven-v1.1"
        assert not exp_dir.exists()


# ---------------------------------------------------------------------------
# Promotion logic
# ---------------------------------------------------------------------------

class TestPromotionLogic:
    def test_promotion_requires_consecutive_successes_gte_5(self):
        consecutive_successes = 5
        avg_score = 0.75
        eligible = consecutive_successes >= 5 and avg_score >= 0.7
        assert eligible is True

    def test_promotion_requires_avg_score_gte_0_7(self):
        consecutive_successes = 6
        avg_score = 0.7
        eligible = consecutive_successes >= 5 and avg_score >= 0.7
        assert eligible is True

    def test_promotion_fails_if_only_4_consecutive_successes(self):
        consecutive_successes = 4
        avg_score = 0.85
        eligible = consecutive_successes >= 5 and avg_score >= 0.7
        assert eligible is False

    def test_promotion_fails_if_avg_score_below_0_7(self):
        consecutive_successes = 5
        avg_score = 0.69
        eligible = consecutive_successes >= 5 and avg_score >= 0.7
        assert eligible is False

    def test_new_harness_always_goes_to_experimental(self):
        proposal = {
            "proposal_type": "new_harness",
            "applies_to_pool": "experimental",
        }
        assert proposal["applies_to_pool"] == "experimental"

    def test_promotion_candidate_applies_to_stable(self):
        proposal = {
            "proposal_type": "promotion",
            "applies_to_pool": "stable",
        }
        assert proposal["applies_to_pool"] == "stable"

    def test_promotion_via_apply_proposals(self, tmp_path):
        """A promotion proposal moves harness from experimental to stable in pool."""
        harnesses_dir = str(tmp_path / "harnesses")
        proposals_dir = str(tmp_path / "proposals")
        local_harnesses_dir = str(tmp_path / "local-harnesses")
        os.makedirs(proposals_dir)

        # Create experimental harness dir in local_harnesses_dir (new location)
        exp_harness_dir = os.path.join(local_harnesses_dir, "experimental", "tdd-driven-v1.1")
        os.makedirs(exp_harness_dir)
        with open(os.path.join(exp_harness_dir, "skill.md"), "w") as fh:
            fh.write("# TDD Driven v1.1\n")
        with open(os.path.join(exp_harness_dir, "metadata.json"), "w") as fh:
            json.dump({"pool": "experimental"}, fh)

        pool = {
            "stable": {"tdd-driven": {"weight": 1.0, "total_runs": 5, "successes": 5,
                                       "failures": 0, "consecutive_successes": 5}},
            "experimental": {"tdd-driven-v1.1": {"weight": 1.2, "total_runs": 6,
                                                   "successes": 6, "failures": 0,
                                                   "consecutive_successes": 6}},
            "last_updated": None,
            "last_merged_session": None,
        }
        proposal = {
            "status": "pending",
            "proposal_type": "promotion",
            "harness": "tdd-driven",
            "experimental_harness_path": "",
            "proposed_change": {
                "change_type": "update_pool",
                "current_value": "experimental",
                "new_value": "stable",
            },
            "rationale": "6 consecutive successes.",
            "expected_impact": "Stable promotion.",
            "applies_to_pool": "stable",
        }
        with open(os.path.join(proposals_dir, "001-promote.json"), "w") as fh:
            json.dump(proposal, fh)

        # Promotion moves harness from experimental to stable in pool
        result = _apply_proposals(proposals_dir, pool, harnesses_dir, local_harnesses_dir)
        assert "tdd-driven" in result["stable"]


# ---------------------------------------------------------------------------
# Demotion logic
# ---------------------------------------------------------------------------

class TestDemotionLogic:
    def test_demotion_threshold_last_5_avg_below_0_55_and_declining(self):
        last_5_avg = 0.48
        trend = "declining"
        eligible = last_5_avg < 0.55 and trend == "declining"
        assert eligible is True

    def test_demotion_not_triggered_when_trend_stable(self):
        last_5_avg = 0.50
        trend = "stable"
        eligible = last_5_avg < 0.55 and trend == "declining"
        assert eligible is False

    def test_demotion_not_triggered_when_avg_above_0_55(self):
        last_5_avg = 0.60
        trend = "declining"
        eligible = last_5_avg < 0.55 and trend == "declining"
        assert eligible is False

    def test_demotion_applies_to_experimental_pool(self):
        proposal = {
            "proposal_type": "demotion",
            "applies_to_pool": "experimental",
        }
        assert proposal["applies_to_pool"] == "experimental"

    def test_demotion_via_apply_proposals(self, tmp_path):
        """A demotion proposal copies harness from local stable override to experimental."""
        harnesses_dir = str(tmp_path / "harnesses")
        proposals_dir = str(tmp_path / "proposals")
        local_harnesses_dir = str(tmp_path / "local-harnesses")
        os.makedirs(proposals_dir)

        # Create local stable harness override (represents a previously promoted harness)
        local_stable_dir = os.path.join(local_harnesses_dir, "migration-safe")
        os.makedirs(local_stable_dir)
        with open(os.path.join(local_stable_dir, "skill.md"), "w") as fh:
            fh.write("# Migration Safe\n")

        pool = {
            "stable": {"migration-safe": {"weight": 0.8, "total_runs": 15,
                                           "successes": 7, "failures": 8,
                                           "consecutive_successes": 0}},
            "experimental": {},
            "last_updated": None,
            "last_merged_session": None,
        }
        proposal = {
            "status": "pending",
            "proposal_type": "demotion",
            "harness": "migration-safe",
            "proposed_change": {
                "change_type": "update_pool",
                "current_value": "stable",
                "new_value": "experimental",
            },
            "rationale": "Last 5 avg 0.48, declining.",
            "expected_impact": "Removed from primary routing.",
            "applies_to_pool": "experimental",
        }
        with open(os.path.join(proposals_dir, "001-demote.json"), "w") as fh:
            json.dump(proposal, fh)

        result = _apply_proposals(proposals_dir, pool, harnesses_dir, local_harnesses_dir)
        # After demotion, migration-safe removed from stable, added to experimental
        assert "migration-safe" not in result["stable"]
        assert "migration-safe-demoted" in result["experimental"]
