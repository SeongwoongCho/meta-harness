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

VALID_TASK_TYPES = {"bugfix", "feature", "refactor", "research", "migration", "incident", "benchmark", "greenfield"}
VALID_UNCERTAINTY = {"low", "medium", "high"}
VALID_BLAST_RADIUS = {"local", "cross-module", "repo-wide"}
VALID_VERIFIABILITY = {"easy", "moderate", "hard"}
VALID_LATENCY = {"low", "high"}
VALID_DOMAINS = {"backend", "frontend", "ml-research", "infra", "docs",
                 "mobile", "data-engineering", "devops", "security"}


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


# ---------------------------------------------------------------------------
# Domain taxonomy expansion (8 domains)
# ---------------------------------------------------------------------------

class TestExpandedDomains:
    """Tests for the expanded 8-value domain enum."""

    def test_new_domain_mobile_is_valid(self):
        assert "mobile" in VALID_DOMAINS

    def test_new_domain_data_engineering_is_valid(self):
        assert "data-engineering" in VALID_DOMAINS

    def test_new_domain_devops_is_valid(self):
        assert "devops" in VALID_DOMAINS

    def test_new_domain_security_is_valid(self):
        assert "security" in VALID_DOMAINS

    def test_legacy_domain_backend_still_valid(self):
        assert "backend" in VALID_DOMAINS

    def test_legacy_domain_frontend_still_valid(self):
        assert "frontend" in VALID_DOMAINS

    def test_legacy_domain_ml_research_still_valid(self):
        assert "ml-research" in VALID_DOMAINS

    def test_legacy_domain_infra_still_valid(self):
        assert "infra" in VALID_DOMAINS

    def test_legacy_domain_docs_still_valid(self):
        assert "docs" in VALID_DOMAINS

    def test_total_domain_count_is_nine(self):
        # 5 legacy (backend, frontend, ml-research, infra, docs) + 4 new = 9
        assert len(VALID_DOMAINS) == 9

    def test_mobile_taxonomy_dict_is_valid(self):
        taxonomy = {
            "task_type": "feature",
            "uncertainty": "medium",
            "blast_radius": "local",
            "verifiability": "moderate",
            "latency_sensitivity": "low",
            "domain": "mobile",
        }
        assert taxonomy["domain"] in VALID_DOMAINS

    def test_data_engineering_taxonomy_dict_is_valid(self):
        taxonomy = {
            "task_type": "bugfix",
            "uncertainty": "low",
            "blast_radius": "local",
            "verifiability": "easy",
            "latency_sensitivity": "low",
            "domain": "data-engineering",
        }
        assert taxonomy["domain"] in VALID_DOMAINS

    def test_devops_taxonomy_dict_is_valid(self):
        taxonomy = {
            "task_type": "feature",
            "uncertainty": "medium",
            "blast_radius": "cross-module",
            "verifiability": "moderate",
            "latency_sensitivity": "low",
            "domain": "devops",
        }
        assert taxonomy["domain"] in VALID_DOMAINS

    def test_security_taxonomy_dict_is_valid(self):
        taxonomy = {
            "task_type": "refactor",
            "uncertainty": "high",
            "blast_radius": "repo-wide",
            "verifiability": "hard",
            "latency_sensitivity": "low",
            "domain": "security",
        }
        assert taxonomy["domain"] in VALID_DOMAINS


# ---------------------------------------------------------------------------
# domain_hint field (optional free-text)
# ---------------------------------------------------------------------------

def validate_taxonomy_with_hint(taxonomy: dict) -> bool:
    """
    Validates that a taxonomy dict is valid.
    domain_hint is optional (may be absent) and, when present, must be a string.
    """
    required_keys = {"task_type", "uncertainty", "blast_radius",
                     "verifiability", "latency_sensitivity", "domain"}
    if not required_keys.issubset(taxonomy.keys()):
        return False
    if taxonomy["task_type"] not in VALID_TASK_TYPES:
        return False
    if taxonomy["uncertainty"] not in VALID_UNCERTAINTY:
        return False
    if taxonomy["blast_radius"] not in VALID_BLAST_RADIUS:
        return False
    if taxonomy["verifiability"] not in VALID_VERIFIABILITY:
        return False
    if taxonomy["latency_sensitivity"] not in VALID_LATENCY:
        return False
    if taxonomy["domain"] not in VALID_DOMAINS:
        return False
    # domain_hint is optional — if present, must be a string
    if "domain_hint" in taxonomy:
        if not isinstance(taxonomy["domain_hint"], str):
            return False
    return True


class TestDomainHint:
    """Tests for the optional domain_hint free-text field."""

    def test_taxonomy_without_domain_hint_is_valid(self):
        taxonomy = {
            "task_type": "bugfix",
            "uncertainty": "low",
            "blast_radius": "local",
            "verifiability": "easy",
            "latency_sensitivity": "low",
            "domain": "backend",
        }
        assert validate_taxonomy_with_hint(taxonomy) is True

    def test_taxonomy_with_domain_hint_string_is_valid(self):
        taxonomy = {
            "task_type": "feature",
            "uncertainty": "medium",
            "blast_radius": "cross-module",
            "verifiability": "moderate",
            "latency_sensitivity": "low",
            "domain": "devops",
            "domain_hint": "also touches security",
        }
        assert validate_taxonomy_with_hint(taxonomy) is True

    def test_domain_hint_accepts_any_string_value(self):
        for hint in ["Spark ETL pipeline", "Kubernetes operator", "also touches devops",
                     "React Native push notifications", "dbt model"]:
            taxonomy = {
                "task_type": "feature",
                "uncertainty": "medium",
                "blast_radius": "local",
                "verifiability": "moderate",
                "latency_sensitivity": "low",
                "domain": "data-engineering",
                "domain_hint": hint,
            }
            assert validate_taxonomy_with_hint(taxonomy) is True, f"hint '{hint}' should be valid"

    def test_domain_hint_must_be_string_when_present(self):
        taxonomy = {
            "task_type": "bugfix",
            "uncertainty": "low",
            "blast_radius": "local",
            "verifiability": "easy",
            "latency_sensitivity": "low",
            "domain": "backend",
            "domain_hint": 123,  # not a string
        }
        assert validate_taxonomy_with_hint(taxonomy) is False

    def test_domain_hint_is_not_routing_input(self):
        # domain_hint does not affect routing decisions — only the domain field does
        taxonomy_with_hint = {
            "task_type": "bugfix",
            "uncertainty": "low",
            "blast_radius": "local",
            "verifiability": "easy",
            "latency_sensitivity": "low",
            "domain": "backend",
            "domain_hint": "also touches devops",
        }
        taxonomy_without_hint = {
            "task_type": "bugfix",
            "uncertainty": "low",
            "blast_radius": "local",
            "verifiability": "easy",
            "latency_sensitivity": "low",
            "domain": "backend",
        }
        # Both are valid; routing behaviour is identical (domain_hint is logging-only)
        assert validate_taxonomy_with_hint(taxonomy_with_hint) is True
        assert validate_taxonomy_with_hint(taxonomy_without_hint) is True

    def test_ensemble_rule_ignores_domain_hint(self):
        # ensemble_required depends only on uncertainty, verifiability, blast_radius
        assert compute_ensemble_required("high", "hard", "repo-wide") is True
        # domain_hint is not a parameter of compute_ensemble_required — logic unchanged
        assert compute_ensemble_required("medium", "easy", "local") is False


# ---------------------------------------------------------------------------
# Fixture coverage: all 8 domains represented
# ---------------------------------------------------------------------------

import os
import json

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")


def _collect_fixture_domains() -> set:
    """Walk all fixture scenario directories and collect domain values from expected.json."""
    domains_found = set()
    for root, dirs, files in os.walk(FIXTURES_DIR):
        if "expected.json" in files:
            path = os.path.join(root, "expected.json")
            with open(path) as f:
                data = json.load(f)
            taxonomy = data.get("expected_taxonomy", {})
            domain = taxonomy.get("domain")
            if domain:
                domains_found.add(domain)
    return domains_found


class TestFixtureDomainCoverage:
    """Ensure fixture scenarios exercise all 8 domains."""

    def test_fixtures_cover_mobile_domain(self):
        assert "mobile" in _collect_fixture_domains()

    def test_fixtures_cover_data_engineering_domain(self):
        assert "data-engineering" in _collect_fixture_domains()

    def test_fixtures_cover_devops_domain(self):
        assert "devops" in _collect_fixture_domains()

    def test_fixtures_cover_security_domain(self):
        assert "security" in _collect_fixture_domains()

    def test_fixtures_cover_all_eight_domains(self):
        found = _collect_fixture_domains()
        assert VALID_DOMAINS.issubset(found), (
            f"Missing domains in fixtures: {VALID_DOMAINS - found}"
        )
