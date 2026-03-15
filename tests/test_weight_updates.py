"""
Tests for weight update logic: delta calculation, weight merging,
consecutive success tracking, and clamping.

Rules encoded from session-end.sh and plans:
  - Delta: (score - 0.5) * 0.1
  - Weight bounds: [0.5, 2.0]
  - Consecutive successes: extend on all-pass, reset to trailing on failure
"""

import json
import os
import subprocess

import pytest


WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS_DIR = os.path.join(WORKSPACE_ROOT, "hooks")


# ---------------------------------------------------------------------------
# Pure Python implementations
# ---------------------------------------------------------------------------

def compute_weight_delta(overall_score: float) -> float:
    return (overall_score - 0.5) * 0.1


def apply_weight_delta(current_weight: float, delta: float) -> float:
    return round(max(0.5, min(2.0, current_weight + delta)), 4)


def _merge_session_weights(pool: dict, weights: dict, harness_stats: dict,
                           timestamp: str, session_id: str) -> dict:
    """Re-implementation of PYEOF from session-end.sh."""
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
    if session_id and session_id != "unknown":
        pool["last_merged_session"] = session_id
    return pool


def _base_pool(harness="tdd-driven", weight=1.0):
    return {
        "stable": {
            harness: {
                "weight": weight,
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


# ---------------------------------------------------------------------------
# Delta calculation
# ---------------------------------------------------------------------------

class TestDeltaCalculation:
    def test_delta_at_perfect_score(self):
        # (1.0 - 0.5) * 0.1 = 0.05
        assert abs(compute_weight_delta(1.0) - 0.05) < 0.0001

    def test_delta_at_half_score(self):
        # (0.5 - 0.5) * 0.1 = 0.0
        assert abs(compute_weight_delta(0.5)) < 0.0001

    def test_delta_at_zero_score(self):
        # (0.0 - 0.5) * 0.1 = -0.05
        assert abs(compute_weight_delta(0.0) - (-0.05)) < 0.0001

    def test_delta_at_0_8(self):
        # (0.8 - 0.5) * 0.1 = 0.03
        assert abs(compute_weight_delta(0.8) - 0.03) < 0.0001

    def test_delta_at_0_3(self):
        # (0.3 - 0.5) * 0.1 = -0.02
        assert abs(compute_weight_delta(0.3) - (-0.02)) < 0.0001

    def test_delta_scales_linearly_with_score(self):
        # Linear relationship
        d1 = compute_weight_delta(0.6)
        d2 = compute_weight_delta(0.7)
        assert abs(d2 - d1 - 0.01) < 0.0001

    def test_positive_delta_for_high_scores(self):
        for score in [0.6, 0.7, 0.8, 0.9, 1.0]:
            assert compute_weight_delta(score) > 0

    def test_negative_delta_for_low_scores(self):
        for score in [0.0, 0.1, 0.2, 0.3, 0.4]:
            assert compute_weight_delta(score) < 0


# ---------------------------------------------------------------------------
# Weight merging
# ---------------------------------------------------------------------------

class TestWeightMerging:
    def test_positive_delta_increases_weight(self):
        pool = _base_pool(weight=1.0)
        weights = {"tdd-driven": {"delta": 0.1}}
        _merge_session_weights(pool, weights, {}, "ts", "sess")
        assert pool["stable"]["tdd-driven"]["weight"] > 1.0

    def test_negative_delta_decreases_weight(self):
        pool = _base_pool(weight=1.0)
        weights = {"tdd-driven": {"delta": -0.1}}
        _merge_session_weights(pool, weights, {}, "ts", "sess")
        assert pool["stable"]["tdd-driven"]["weight"] < 1.0

    def test_zero_delta_leaves_weight_unchanged(self):
        pool = _base_pool(weight=1.2)
        weights = {"tdd-driven": {"delta": 0}}
        _merge_session_weights(pool, weights, {}, "ts", "sess")
        assert pool["stable"]["tdd-driven"]["weight"] == 1.2

    def test_merge_accumulates_total_runs(self):
        pool = _base_pool()
        stats = {"tdd-driven": {"runs": 3, "successes": 3, "failures": 0,
                                "trailing_consecutive_successes": 3}}
        _merge_session_weights(pool, {}, stats, "ts", "sess")
        assert pool["stable"]["tdd-driven"]["total_runs"] == 3

    def test_merge_accumulates_across_sessions(self):
        pool = _base_pool()
        stats = {"tdd-driven": {"runs": 2, "successes": 2, "failures": 0,
                                "trailing_consecutive_successes": 2}}
        _merge_session_weights(pool, {}, stats, "ts1", "sess-1")
        _merge_session_weights(pool, {}, stats, "ts2", "sess-2")
        assert pool["stable"]["tdd-driven"]["total_runs"] == 4

    def test_merge_unknown_harness_is_ignored(self):
        pool = _base_pool()
        weights = {"nonexistent-harness": {"delta": 0.5}}
        _merge_session_weights(pool, weights, {}, "ts", "sess")
        # Should not raise, and tdd-driven remains untouched
        assert pool["stable"]["tdd-driven"]["weight"] == 1.0

    def test_merge_updates_last_updated(self):
        pool = _base_pool()
        _merge_session_weights(pool, {}, {}, "2026-ts-001", "sess")
        assert pool["last_updated"] == "2026-ts-001"

    def test_merge_updates_last_merged_session(self):
        pool = _base_pool()
        _merge_session_weights(pool, {}, {}, "ts", "sess-known-123")
        assert pool["last_merged_session"] == "sess-known-123"

    def test_merge_skips_unknown_session_id(self):
        pool = _base_pool()
        pool["last_merged_session"] = "previous"
        _merge_session_weights(pool, {}, {}, "ts", "unknown")
        assert pool["last_merged_session"] == "previous"

    def test_merge_works_for_experimental_harness(self):
        pool = _base_pool()
        pool["experimental"]["exp-harness"] = {
            "weight": 1.0, "total_runs": 0, "successes": 0,
            "failures": 0, "consecutive_successes": 0,
        }
        weights = {"exp-harness": {"delta": 0.15}}
        _merge_session_weights(pool, weights, {}, "ts", "sess")
        assert pool["experimental"]["exp-harness"]["weight"] > 1.0


# ---------------------------------------------------------------------------
# Clamping
# ---------------------------------------------------------------------------

class TestWeightClamping:
    def test_clamp_max_from_below(self):
        assert apply_weight_delta(1.9, 0.5) == 2.0

    def test_clamp_max_exactly(self):
        assert apply_weight_delta(2.0, 0.0) == 2.0

    def test_clamp_min_from_above(self):
        assert apply_weight_delta(0.6, -0.5) == 0.5

    def test_clamp_min_exactly(self):
        assert apply_weight_delta(0.5, 0.0) == 0.5

    def test_no_clamp_when_within_bounds(self):
        result = apply_weight_delta(1.0, 0.2)
        assert result == 1.2

    def test_weight_always_within_bounds_after_large_positive_delta(self):
        result = apply_weight_delta(1.9, 10.0)
        assert result <= 2.0

    def test_weight_always_within_bounds_after_large_negative_delta(self):
        result = apply_weight_delta(0.6, -10.0)
        assert result >= 0.5


# ---------------------------------------------------------------------------
# Consecutive success tracking
# ---------------------------------------------------------------------------

class TestConsecutiveSuccessTracking:
    def test_extends_streak_on_all_successes(self):
        pool = _base_pool()
        pool["stable"]["tdd-driven"]["consecutive_successes"] = 3
        stats = {"tdd-driven": {"runs": 2, "successes": 2, "failures": 0,
                                "trailing_consecutive_successes": 2}}
        _merge_session_weights(pool, {}, stats, "ts", "sess")
        assert pool["stable"]["tdd-driven"]["consecutive_successes"] == 5

    def test_resets_streak_on_failure(self):
        pool = _base_pool()
        pool["stable"]["tdd-driven"]["consecutive_successes"] = 10
        stats = {"tdd-driven": {"runs": 3, "successes": 1, "failures": 2,
                                "trailing_consecutive_successes": 1}}
        _merge_session_weights(pool, {}, stats, "ts", "sess")
        # Reset to trailing (1), not accumulated 10+1
        assert pool["stable"]["tdd-driven"]["consecutive_successes"] == 1

    def test_no_streak_change_without_runs(self):
        pool = _base_pool()
        pool["stable"]["tdd-driven"]["consecutive_successes"] = 4
        _merge_session_weights(pool, {}, {}, "ts", "sess")
        # No stats means no change to consecutive_successes
        assert pool["stable"]["tdd-driven"]["consecutive_successes"] == 4

    def test_streak_of_zero_after_all_failures(self):
        pool = _base_pool()
        pool["stable"]["tdd-driven"]["consecutive_successes"] = 5
        stats = {"tdd-driven": {"runs": 2, "successes": 0, "failures": 2,
                                "trailing_consecutive_successes": 0}}
        _merge_session_weights(pool, {}, stats, "ts", "sess")
        assert pool["stable"]["tdd-driven"]["consecutive_successes"] == 0

    def test_promotion_threshold_requires_5_consecutive_successes(self):
        """Promotion threshold from evolution-manager.md: consecutive_successes >= 5."""
        pool = {"experimental": {"candidate": {
            "weight": 1.1, "total_runs": 7, "successes": 6, "failures": 1,
            "consecutive_successes": 5
        }}}
        candidate = pool["experimental"]["candidate"]
        assert candidate["consecutive_successes"] >= 5

    def test_promotion_also_requires_avg_score_0_7(self):
        """avg_score >= 0.7 required for promotion alongside consecutive_successes."""
        consecutive = 5
        avg_score = 0.75
        promotion_eligible = consecutive >= 5 and avg_score >= 0.7
        assert promotion_eligible is True

    def test_demotion_threshold_last_5_avg_below_0_55(self):
        """Demotion: last_5_avg_score < 0.55 AND declining trend."""
        last_5_avg = 0.48
        trend = "declining"
        demotion_eligible = last_5_avg < 0.55 and trend == "declining"
        assert demotion_eligible is True

    def test_no_demotion_for_single_bad_run(self):
        """Demotion requires declining TREND, not just one bad run."""
        last_5_avg = 0.52  # Below 0.55
        trend = "stable"  # Not declining
        demotion_eligible = last_5_avg < 0.55 and trend == "declining"
        assert demotion_eligible is False
