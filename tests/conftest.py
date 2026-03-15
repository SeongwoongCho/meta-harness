"""
Shared fixtures for adaptive-harness comprehensive test suite.
"""

import json
import os
import shutil

import pytest

# Derive paths dynamically so tests work both locally and in CI
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Plugin root mirrors the repo layout (agents/, harnesses/, patterns/ are in the repo)
PLUGIN_ROOT = WORKSPACE_ROOT
HOOKS_DIR = os.path.join(WORKSPACE_ROOT, "hooks")


@pytest.fixture
def plugin_root():
    return PLUGIN_ROOT


@pytest.fixture
def hooks_dir():
    return HOOKS_DIR


@pytest.fixture
def workspace_root():
    return WORKSPACE_ROOT


@pytest.fixture
def tmp_state_dir(tmp_path):
    """A temporary .adaptive-harness state directory with standard subdirectories."""
    state_dir = tmp_path / ".adaptive-harness"
    state_dir.mkdir()
    (state_dir / "sessions").mkdir()
    (state_dir / "evaluation-logs").mkdir()
    (state_dir / "evolution-proposals").mkdir()
    return state_dir


@pytest.fixture
def sample_pool():
    """A minimal harness pool with one stable harness."""
    return {
        "stable": {
            "tdd-driven": {
                "weight": 1.0,
                "total_runs": 0,
                "successes": 0,
                "failures": 0,
                "consecutive_successes": 0,
            }
        },
        "experimental": {},
        "last_updated": None,
        "last_merged_session": None,
    }


@pytest.fixture
def full_pool():
    """A pool with multiple stable harnesses matching the actual harness set."""
    harnesses = [
        "tdd-driven",
        "systematic-debugging",
        "rapid-prototype",
        "research-iteration",
        "careful-refactor",
        "code-review",
        "migration-safe",
        "ralplan-consensus",
        "ralph-loop",
        "spike-then-harden",
        "divide-and-conquer",
        "adversarial-review",
        "progressive-refinement",
    ]
    pool = {
        "stable": {
            name: {
                "weight": 1.0,
                "total_runs": 0,
                "successes": 0,
                "failures": 0,
                "consecutive_successes": 0,
            }
            for name in harnesses
        },
        "experimental": {},
        "last_updated": None,
        "last_merged_session": None,
    }
    return pool


@pytest.fixture
def sample_eval_json():
    """A minimal valid evaluation JSON record."""
    return {
        "run_id": "test-run-001",
        "harness_used": "tdd-driven",
        "harness": "tdd-driven",
        "scores": {
            "correctness": 0.9,
            "completeness": 0.85,
            "quality": 0.80,
            "robustness": 0.75,
            "clarity": 0.85,
            "verifiability": 0.70,
        },
        "overall_score": 0.8275,
        "quality_gate_results": {
            "hooks_passed": True,
            "evidence_collected": True,
            "evaluator_approved": True,
        },
        "quality_gate_passed": True,
        "fast_path": False,
        "improvement_suggestions": [],
        "evidence_summary": {
            "build_commands_found": [],
            "test_commands_found": [],
            "lint_commands_found": [],
            "total_evidence_files": 0,
        },
        "scoring_notes": "Test fixture.",
    }


@pytest.fixture
def sample_evidence():
    """A valid evidence file structure as produced by collect-evidence.sh."""
    return {
        "timestamp": "20260315T000000Z",
        "session_id": "test-session-001",
        "tool": "Bash",
        "command": "python -m pytest tests/ -v",
        "stdout": "===== 5 passed in 0.12s =====",
        "stderr": "",
        "exit_code": 0,
    }


@pytest.fixture
def sample_proposal():
    """A minimal content_modification proposal."""
    return {
        "proposal_id": "tdd-driven-skill-mod-20260315-a3f2b1",
        "created_at": "2026-03-15T10:00:00Z",
        "harness": "tdd-driven",
        "proposal_type": "content_modification",
        "target_file": "skill.md",
        "priority": "high",
        "status": "pending",
        "evidence": {
            "evaluation_count": 5,
            "affected_dimension": "robustness",
            "dimension_avg_score": 0.52,
        },
        "rationale": "robustness scores consistently below threshold.",
        "proposed_change": {
            "description": "Add error handling review step",
            "file_path": "harnesses/tdd-driven/skill.md",
            "change_type": "add_section",
            "location": "end",
            "content": "## Error Handling Review\nCheck all error paths.",
        },
        "expected_impact": "Increase robustness from ~0.52 to ~0.75",
        "applies_to_pool": "experimental",
        "experimental_harness_path": "harnesses/experimental/tdd-driven-v1.1",
    }
