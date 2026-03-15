"""
Tests for evaluation logic: 6-dimension weighted scoring, quality gate logic,
eval JSON schema, and fast-path eval.

Rules from agents/evaluator.md:
  - Weights: correctness=0.25, completeness=0.20, quality=0.20, robustness=0.10,
             clarity=0.15, verifiability=0.10
  - Quality gate: overall_score >= 0.7 AND correctness >= 0.5
  - evaluator_approved: true if overall_score >= 0.7 AND correctness >= 0.5
"""

import json
import math

import pytest


# ---------------------------------------------------------------------------
# Pure Python implementations of evaluator rules
# ---------------------------------------------------------------------------

DIMENSION_WEIGHTS = {
    "correctness": 0.25,
    "completeness": 0.20,
    "quality": 0.20,
    "robustness": 0.10,
    "clarity": 0.15,
    "verifiability": 0.10,
}


def compute_overall_score(scores: dict) -> float:
    """Compute weighted overall score from dimension scores."""
    return sum(scores[dim] * weight for dim, weight in DIMENSION_WEIGHTS.items())


def evaluator_approved(overall_score: float, correctness: float) -> bool:
    """Quality gate: overall_score >= 0.7 AND correctness >= 0.5"""
    return overall_score >= 0.7 and correctness >= 0.5


def quality_gate_passed(scores: dict) -> bool:
    overall = compute_overall_score(scores)
    return evaluator_approved(overall, scores["correctness"])


REQUIRED_EVAL_FIELDS = {
    "run_id",
    "harness_used",
    "scores",
    "overall_score",
    "quality_gate_results",
    "improvement_suggestions",
    "evidence_summary",
    "scoring_notes",
}

REQUIRED_SCORE_DIMENSIONS = {
    "correctness",
    "completeness",
    "quality",
    "robustness",
    "clarity",
    "verifiability",
}

REQUIRED_QUALITY_GATE_FIELDS = {
    "hooks_passed",
    "evidence_collected",
    "evaluator_approved",
}


# ---------------------------------------------------------------------------
# Weighted score computation
# ---------------------------------------------------------------------------

class TestWeightedScoreComputation:
    def test_weights_sum_to_1_0(self):
        total = sum(DIMENSION_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_perfect_scores_give_1_0(self):
        scores = {dim: 1.0 for dim in DIMENSION_WEIGHTS}
        result = compute_overall_score(scores)
        assert abs(result - 1.0) < 0.001

    def test_zero_scores_give_0_0(self):
        scores = {dim: 0.0 for dim in DIMENSION_WEIGHTS}
        result = compute_overall_score(scores)
        assert abs(result) < 0.001

    def test_all_0_5_gives_0_5(self):
        scores = {dim: 0.5 for dim in DIMENSION_WEIGHTS}
        result = compute_overall_score(scores)
        assert abs(result - 0.5) < 0.001

    def test_specific_scores_match_documented_example(self):
        # From evaluator.md output example: scores below
        scores = {
            "correctness": 0.90,
            "completeness": 0.85,
            "quality": 0.80,
            "robustness": 0.75,
            "clarity": 0.85,
            "verifiability": 0.70,
        }
        # expected = 0.90*0.25 + 0.85*0.20 + 0.80*0.20 + 0.75*0.10 + 0.85*0.15 + 0.70*0.10
        expected = 0.225 + 0.17 + 0.16 + 0.075 + 0.1275 + 0.07
        result = compute_overall_score(scores)
        assert abs(result - expected) < 0.001

    def test_correctness_has_highest_weight(self):
        assert DIMENSION_WEIGHTS["correctness"] == max(DIMENSION_WEIGHTS.values())

    def test_robustness_has_lowest_weight(self):
        assert DIMENSION_WEIGHTS["robustness"] == min(DIMENSION_WEIGHTS.values())

    def test_all_six_dimensions_present_in_weights(self):
        assert set(DIMENSION_WEIGHTS.keys()) == REQUIRED_SCORE_DIMENSIONS


# ---------------------------------------------------------------------------
# Quality gate logic
# ---------------------------------------------------------------------------

class TestQualityGate:
    def test_gate_passes_when_score_0_7_and_correctness_0_5(self):
        scores = {
            "correctness": 0.5, "completeness": 0.7, "quality": 0.8,
            "robustness": 0.8, "clarity": 0.8, "verifiability": 0.8,
        }
        # overall > 0.7, correctness == 0.5
        overall = compute_overall_score(scores)
        assert evaluator_approved(overall, scores["correctness"]) is True

    def test_gate_fails_when_overall_below_0_7(self):
        # All 0.5 gives overall == 0.5 < 0.7
        scores = {dim: 0.5 for dim in DIMENSION_WEIGHTS}
        assert quality_gate_passed(scores) is False

    def test_gate_fails_when_correctness_below_0_5(self):
        # High overall but low correctness
        scores = {
            "correctness": 0.4, "completeness": 1.0, "quality": 1.0,
            "robustness": 1.0, "clarity": 1.0, "verifiability": 1.0,
        }
        assert quality_gate_passed(scores) is False

    def test_gate_fails_when_both_below_threshold(self):
        scores = {dim: 0.3 for dim in DIMENSION_WEIGHTS}
        assert quality_gate_passed(scores) is False

    def test_gate_passes_for_perfect_scores(self):
        scores = {dim: 1.0 for dim in DIMENSION_WEIGHTS}
        assert quality_gate_passed(scores) is True

    def test_gate_evaluator_approved_boundary_exactly_0_7(self):
        assert evaluator_approved(0.7, 0.5) is True

    def test_gate_evaluator_approved_boundary_just_below_0_7(self):
        assert evaluator_approved(0.699, 0.5) is False

    def test_gate_evaluator_approved_correctness_exactly_0_5(self):
        assert evaluator_approved(0.8, 0.5) is True

    def test_gate_evaluator_approved_correctness_just_below_0_5(self):
        assert evaluator_approved(0.8, 0.499) is False

    def test_correctness_zero_fails_gate_regardless_of_overall(self):
        # Override: correctness=0.0 always fails
        assert evaluator_approved(0.9, 0.0) is False


# ---------------------------------------------------------------------------
# Eval JSON schema validation
# ---------------------------------------------------------------------------

class TestEvalJsonSchema:
    def test_eval_json_has_required_fields(self, sample_eval_json):
        for field in REQUIRED_EVAL_FIELDS:
            assert field in sample_eval_json, f"Missing required field: {field}"

    def test_eval_json_scores_has_all_dimensions(self, sample_eval_json):
        for dim in REQUIRED_SCORE_DIMENSIONS:
            assert dim in sample_eval_json["scores"], f"Missing dimension: {dim}"

    def test_eval_json_quality_gate_results_has_required_fields(self, sample_eval_json):
        qg = sample_eval_json["quality_gate_results"]
        for field in REQUIRED_QUALITY_GATE_FIELDS:
            assert field in qg, f"Missing quality_gate field: {field}"

    def test_eval_json_scores_are_between_0_and_1(self, sample_eval_json):
        for dim, score in sample_eval_json["scores"].items():
            assert 0.0 <= score <= 1.0, f"{dim} score out of range: {score}"

    def test_eval_json_overall_score_is_between_0_and_1(self, sample_eval_json):
        assert 0.0 <= sample_eval_json["overall_score"] <= 1.0

    def test_eval_json_harness_used_is_string(self, sample_eval_json):
        assert isinstance(sample_eval_json["harness_used"], str)

    def test_eval_json_run_id_is_string(self, sample_eval_json):
        assert isinstance(sample_eval_json["run_id"], str)

    def test_eval_json_improvement_suggestions_is_list(self, sample_eval_json):
        assert isinstance(sample_eval_json["improvement_suggestions"], list)

    def test_eval_json_can_be_serialized(self, sample_eval_json):
        serialized = json.dumps(sample_eval_json)
        loaded = json.loads(serialized)
        assert loaded["harness_used"] == sample_eval_json["harness_used"]

    def test_eval_json_quality_gate_passed_matches_gate_logic(self, sample_eval_json):
        """The quality_gate_passed field should be consistent with evaluator rules."""
        scores = sample_eval_json["scores"]
        expected = quality_gate_passed(scores)
        assert sample_eval_json["quality_gate_passed"] == expected


# ---------------------------------------------------------------------------
# Fast-path eval
# ---------------------------------------------------------------------------

class TestFastPathEval:
    def test_fast_path_eval_skips_scoring(self):
        eval_record = {
            "run_id": "fast-path-001",
            "harness_used": "fast-path",
            "harness": "fast-path",
            "fast_path": True,
            "quality_gate_passed": True,
        }
        assert eval_record["fast_path"] is True

    def test_fast_path_eval_not_included_in_harness_stats(self):
        """Session-end.sh skips eval files where fast_path=True."""
        evals = [
            {"harness": "tdd-driven", "fast_path": True, "quality_gate_passed": True},
            {"harness": "tdd-driven", "fast_path": False, "quality_gate_passed": True},
        ]
        # Only non-fast-path evals count
        counted = [e for e in evals if not e.get("fast_path")]
        assert len(counted) == 1

    def test_non_fast_path_eval_has_full_scores(self, sample_eval_json):
        assert sample_eval_json["fast_path"] is False
        assert "scores" in sample_eval_json
        assert len(sample_eval_json["scores"]) == 6


# ---------------------------------------------------------------------------
# Score dimension rubric tests
# ---------------------------------------------------------------------------

class TestScoreRubrics:
    def test_correctness_rubric_1_0(self):
        """1.0: All requirements met, no errors."""
        score = 1.0
        assert 0.0 <= score <= 1.0

    def test_correctness_rubric_0_7(self):
        """0.7: Most requirements met, minor gaps."""
        score = 0.7
        assert score >= 0.7

    def test_quality_gate_at_0_7_correctness_passes_when_overall_high(self):
        scores = {
            "correctness": 0.7, "completeness": 0.8, "quality": 0.8,
            "robustness": 0.7, "clarity": 0.8, "verifiability": 0.7,
        }
        assert quality_gate_passed(scores) is True

    def test_all_dimensions_have_positive_weights(self):
        for dim, w in DIMENSION_WEIGHTS.items():
            assert w > 0, f"Dimension {dim} has non-positive weight"
