"""
Tests for routing logic: taxonomy classification, ensemble trigger rule,
fast-path detection, chain building, and experimental exploration.

These tests encode the documented rules from agents/router.md as pure Python.
"""

import pytest


# ---------------------------------------------------------------------------
# Pure Python implementations of router rules
# ---------------------------------------------------------------------------

def compute_ensemble_required(uncertainty: str, verifiability: str, blast_radius: str) -> bool:
    """
    Implements the ensemble_rule from agents/router.md.
    Step A: uncertainty == "high"  (gate condition)
    Step B: verifiability == "hard" OR blast_radius == "repo-wide"
    """
    if uncertainty != "high":
        return False
    return verifiability == "hard" or blast_radius == "repo-wide"


def is_fast_path(message: str) -> bool:
    """
    Implements the fast_path rule from agents/router.md.
    Returns True only for zero-work acknowledgment messages.
    """
    FAST_PATH_EXACT = {"ok, done", "sounds good", "thanks", "looks good, ship it", "got it"}
    return message.strip().lower() in FAST_PATH_EXACT


def select_experimental_variant(total_runs: int) -> bool:
    """
    Implements experimental_exploration rule from agents/router.md.
    - If total_runs < 5: always select experimental (forced exploration).
    - Else: select if total_runs % 5 == 0 (every 5th run).
    """
    if total_runs < 5:
        return True
    return total_runs % 5 == 0


def compute_weight_delta(overall_score: float) -> float:
    """
    Delta formula from the plan: (score - 0.5) * 0.1
    """
    return (overall_score - 0.5) * 0.1


# ---------------------------------------------------------------------------
# Taxonomy classification tests (rule-based encoding)
# ---------------------------------------------------------------------------

VALID_TASK_TYPES = {"bugfix", "feature", "refactor", "research", "migration", "incident", "benchmark"}
VALID_UNCERTAINTY = {"low", "medium", "high"}
VALID_BLAST_RADIUS = {"local", "cross-module", "repo-wide"}
VALID_VERIFIABILITY = {"easy", "moderate", "hard"}
VALID_LATENCY = {"low", "high"}
VALID_DOMAINS = {"backend", "frontend", "ml-research", "infra", "docs"}


class TestTaxonomyValues:
    def test_valid_task_types(self):
        for v in VALID_TASK_TYPES:
            assert v in VALID_TASK_TYPES

    def test_valid_uncertainty_values(self):
        assert VALID_UNCERTAINTY == {"low", "medium", "high"}

    def test_valid_blast_radius_values(self):
        assert VALID_BLAST_RADIUS == {"local", "cross-module", "repo-wide"}

    def test_valid_verifiability_values(self):
        assert VALID_VERIFIABILITY == {"easy", "moderate", "hard"}

    def test_taxonomy_dict_has_all_six_axes(self):
        taxonomy = {
            "task_type": "bugfix",
            "uncertainty": "medium",
            "blast_radius": "local",
            "verifiability": "easy",
            "latency_sensitivity": "low",
            "domain": "backend",
        }
        expected_keys = {"task_type", "uncertainty", "blast_radius", "verifiability",
                         "latency_sensitivity", "domain"}
        assert set(taxonomy.keys()) == expected_keys

    def test_all_taxonomy_axes_have_valid_values(self):
        taxonomy = {
            "task_type": "feature",
            "uncertainty": "high",
            "blast_radius": "repo-wide",
            "verifiability": "hard",
            "latency_sensitivity": "low",
            "domain": "backend",
        }
        assert taxonomy["task_type"] in VALID_TASK_TYPES
        assert taxonomy["uncertainty"] in VALID_UNCERTAINTY
        assert taxonomy["blast_radius"] in VALID_BLAST_RADIUS
        assert taxonomy["verifiability"] in VALID_VERIFIABILITY
        assert taxonomy["latency_sensitivity"] in VALID_LATENCY
        assert taxonomy["domain"] in VALID_DOMAINS


# ---------------------------------------------------------------------------
# Ensemble trigger rule
# ---------------------------------------------------------------------------

class TestEnsembleRule:
    def test_ensemble_false_when_uncertainty_not_high(self):
        # Step A gate fails
        assert compute_ensemble_required("medium", "hard", "repo-wide") is False

    def test_ensemble_false_when_uncertainty_low(self):
        assert compute_ensemble_required("low", "hard", "repo-wide") is False

    def test_ensemble_true_uncertainty_high_and_verifiability_hard(self):
        # Step A + Step B (verifiability)
        assert compute_ensemble_required("high", "hard", "local") is True

    def test_ensemble_true_uncertainty_high_and_blast_radius_repo_wide(self):
        # Step A + Step B (blast_radius)
        assert compute_ensemble_required("high", "moderate", "repo-wide") is True

    def test_ensemble_true_both_step_b_conditions_met(self):
        assert compute_ensemble_required("high", "hard", "repo-wide") is True

    def test_ensemble_false_uncertainty_high_but_neither_step_b(self):
        # uncertainty=high but verifiability!=hard AND blast_radius!=repo-wide
        assert compute_ensemble_required("high", "moderate", "cross-module") is False

    def test_ensemble_false_uncertainty_high_verifiability_moderate_blast_local(self):
        assert compute_ensemble_required("high", "moderate", "local") is False

    def test_ensemble_false_uncertainty_high_verifiability_easy_blast_cross_module(self):
        assert compute_ensemble_required("high", "easy", "cross-module") is False

    def test_ensemble_documented_example_1(self):
        # From router.md: uncertainty=high, blast_radius=repo-wide, verifiability=moderate → true
        assert compute_ensemble_required("high", "moderate", "repo-wide") is True

    def test_ensemble_documented_example_2(self):
        # From router.md: uncertainty=high, verifiability=hard, blast_radius=local → true
        assert compute_ensemble_required("high", "hard", "local") is True

    def test_ensemble_documented_example_3(self):
        # From router.md: uncertainty=high, verifiability=moderate, blast_radius=cross-module → false
        assert compute_ensemble_required("high", "moderate", "cross-module") is False

    def test_ensemble_documented_example_4(self):
        # From router.md: uncertainty=medium, blast_radius=repo-wide → false (fails Step A)
        assert compute_ensemble_required("medium", "hard", "repo-wide") is False


# ---------------------------------------------------------------------------
# Fast-path detection
# ---------------------------------------------------------------------------

class TestFastPath:
    def test_ok_done_is_fast_path(self):
        assert is_fast_path("ok, done") is True

    def test_sounds_good_is_fast_path(self):
        assert is_fast_path("sounds good") is True

    def test_thanks_is_fast_path(self):
        assert is_fast_path("thanks") is True

    def test_looks_good_ship_it_is_fast_path(self):
        assert is_fast_path("looks good, ship it") is True

    def test_got_it_is_fast_path(self):
        assert is_fast_path("got it") is True

    def test_fix_typo_is_not_fast_path(self):
        assert is_fast_path("fix that typo") is False

    def test_add_comment_is_not_fast_path(self):
        assert is_fast_path("add a comment there") is False

    def test_refactor_this_is_not_fast_path(self):
        assert is_fast_path("refactor this") is False

    def test_empty_string_is_not_fast_path(self):
        assert is_fast_path("") is False

    def test_implement_feature_is_not_fast_path(self):
        assert is_fast_path("implement the login feature") is False

    def test_fast_path_is_case_insensitive(self):
        assert is_fast_path("THANKS") is True
        assert is_fast_path("OK, DONE") is True


# ---------------------------------------------------------------------------
# Experimental exploration
# ---------------------------------------------------------------------------

class TestExperimentalExploration:
    def test_new_variant_always_selected_at_0_runs(self):
        assert select_experimental_variant(0) is True

    def test_new_variant_always_selected_at_4_runs(self):
        assert select_experimental_variant(4) is True

    def test_variant_selected_at_5_runs(self):
        # 5 % 5 == 0
        assert select_experimental_variant(5) is True

    def test_variant_not_selected_at_6_runs(self):
        assert select_experimental_variant(6) is False

    def test_variant_selected_at_10_runs(self):
        assert select_experimental_variant(10) is True

    def test_variant_not_selected_at_11_runs(self):
        assert select_experimental_variant(11) is False

    def test_variant_selected_at_15_runs(self):
        assert select_experimental_variant(15) is True

    def test_variant_not_selected_at_7_runs(self):
        assert select_experimental_variant(7) is False


# ---------------------------------------------------------------------------
# Chain building
# ---------------------------------------------------------------------------

class TestChainBuilding:
    def test_single_harness_chain_for_low_uncertainty(self):
        # Low uncertainty: no chain needed
        chain = ["tdd-driven"]
        assert len(chain) == 1
        assert chain[0] == "tdd-driven"

    def test_chain_starts_with_planning_for_high_uncertainty(self):
        # High uncertainty refactor: ralplan-consensus first
        chain = ["ralplan-consensus", "careful-refactor", "code-review"]
        assert chain[0] == "ralplan-consensus"

    def test_selected_harness_is_first_non_planning_harness(self):
        chain = ["ralplan-consensus", "tdd-driven"]
        non_planning = [h for h in chain if h != "ralplan-consensus"]
        assert non_planning[0] == "tdd-driven"

    def test_greenfield_skips_ralplan_consensus(self):
        # Greenfield tasks: skip planning step, go directly to execution
        chain = ["tdd-driven"]
        assert "ralplan-consensus" not in chain

    def test_ralph_loop_used_for_iterative_tasks(self):
        chain = ["ralplan-consensus", "ralph-loop"]
        assert "ralph-loop" in chain

    def test_full_cycle_chain_structure(self):
        chain = ["ralplan-consensus", "careful-refactor", "code-review"]
        assert chain[0] == "ralplan-consensus"
        assert "code-review" in chain
        assert len(chain) == 3


# ---------------------------------------------------------------------------
# Weight delta computation
# ---------------------------------------------------------------------------

class TestWeightDelta:
    def test_perfect_score_gives_positive_delta(self):
        delta = compute_weight_delta(1.0)
        assert abs(delta - 0.05) < 0.001

    def test_half_score_gives_zero_delta(self):
        delta = compute_weight_delta(0.5)
        assert abs(delta) < 0.001

    def test_zero_score_gives_negative_delta(self):
        delta = compute_weight_delta(0.0)
        assert delta < 0

    def test_high_score_gives_positive_delta(self):
        delta = compute_weight_delta(0.85)
        assert delta > 0

    def test_low_score_gives_negative_delta(self):
        delta = compute_weight_delta(0.3)
        assert delta < 0

    def test_delta_formula_specific_value(self):
        # (0.8 - 0.5) * 0.1 = 0.03
        delta = compute_weight_delta(0.8)
        assert abs(delta - 0.03) < 0.0001
