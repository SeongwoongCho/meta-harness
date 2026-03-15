"""
Tests for harness pool CRUD, weight bounds, pool versioning,
bootstrap logic, and schema validation.
"""

import json
import os
import subprocess

import pytest


WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN_ROOT = WORKSPACE_ROOT
HOOKS_DIR = os.path.join(WORKSPACE_ROOT, "hooks")

STABLE_HARNESS_NAMES = [
    "adversarial-review",
    "careful-refactor",
    "code-review",
    "divide-and-conquer",
    "migration-safe",
    "progressive-refinement",
    "ralph-loop",
    "ralplan-consensus",
    "rapid-prototype",
    "research-iteration",
    "spike-then-harden",
    "systematic-debugging",
    "tdd-driven",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bootstrap_pool(harnesses_dir: str, pool_file: str) -> dict:
    """Run the BOOTSTRAP_POOL heredoc from session-start.sh and return parsed pool."""
    session_start_sh = os.path.join(HOOKS_DIR, "session-start.sh")
    with open(session_start_sh) as fh:
        content = fh.read()
    start = content.find("<<'BOOTSTRAP_POOL'\n") + len("<<'BOOTSTRAP_POOL'\n")
    end = content.find("\nBOOTSTRAP_POOL", start)
    code = content[start:end]
    proc = subprocess.run(
        ["python3", "-", harnesses_dir, pool_file],
        input=code,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"BOOTSTRAP_POOL failed: {proc.stderr}"
    with open(pool_file) as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Pool schema validation
# ---------------------------------------------------------------------------

class TestPoolSchema:
    def test_pool_has_stable_key(self, sample_pool):
        assert "stable" in sample_pool

    def test_pool_has_experimental_key(self, sample_pool):
        assert "experimental" in sample_pool

    def test_pool_has_last_updated(self, sample_pool):
        assert "last_updated" in sample_pool

    def test_pool_has_last_merged_session(self, sample_pool):
        assert "last_merged_session" in sample_pool

    def test_harness_entry_has_required_fields(self, sample_pool):
        entry = sample_pool["stable"]["tdd-driven"]
        for field in ("weight", "total_runs", "successes", "failures", "consecutive_successes"):
            assert field in entry, f"Missing field: {field}"

    def test_default_weight_is_1_0(self, sample_pool):
        assert sample_pool["stable"]["tdd-driven"]["weight"] == 1.0

    def test_default_counters_are_zero(self, sample_pool):
        entry = sample_pool["stable"]["tdd-driven"]
        assert entry["total_runs"] == 0
        assert entry["successes"] == 0
        assert entry["failures"] == 0
        assert entry["consecutive_successes"] == 0


# ---------------------------------------------------------------------------
# Weight bounds
# ---------------------------------------------------------------------------

class TestWeightBounds:
    def _apply_delta(self, pool, harness_name, delta):
        """Apply a weight delta directly to the pool entry."""
        entry = pool["stable"][harness_name]
        current = entry.get("weight", 1.0)
        entry["weight"] = round(max(0.5, min(2.0, current + delta)), 4)
        return entry

    def test_weight_clamped_to_max_2_0(self, sample_pool):
        sample_pool["stable"]["tdd-driven"]["weight"] = 1.95
        entry = self._apply_delta(sample_pool, "tdd-driven", 0.5)
        assert entry["weight"] == 2.0

    def test_weight_clamped_to_min_0_5(self, sample_pool):
        sample_pool["stable"]["tdd-driven"]["weight"] = 0.55
        entry = self._apply_delta(sample_pool, "tdd-driven", -0.5)
        assert entry["weight"] == 0.5

    def test_weight_delta_positive(self, sample_pool):
        entry = self._apply_delta(sample_pool, "tdd-driven", 0.2)
        assert abs(entry["weight"] - 1.2) < 0.001

    def test_weight_delta_negative(self, sample_pool):
        entry = self._apply_delta(sample_pool, "tdd-driven", -0.1)
        assert abs(entry["weight"] - 0.9) < 0.001

    def test_weight_exactly_at_min(self, sample_pool):
        sample_pool["stable"]["tdd-driven"]["weight"] = 0.5
        entry = self._apply_delta(sample_pool, "tdd-driven", 0.0)
        assert entry["weight"] == 0.5

    def test_weight_exactly_at_max(self, sample_pool):
        sample_pool["stable"]["tdd-driven"]["weight"] = 2.0
        entry = self._apply_delta(sample_pool, "tdd-driven", 0.0)
        assert entry["weight"] == 2.0


# ---------------------------------------------------------------------------
# Pool CRUD operations
# ---------------------------------------------------------------------------

class TestPoolCRUD:
    def test_add_harness_to_stable(self, sample_pool):
        sample_pool["stable"]["new-harness"] = {
            "weight": 1.0, "total_runs": 0, "successes": 0,
            "failures": 0, "consecutive_successes": 0,
        }
        assert "new-harness" in sample_pool["stable"]

    def test_add_harness_to_experimental(self, sample_pool):
        sample_pool["experimental"]["exp-harness"] = {
            "weight": 1.0, "total_runs": 0, "successes": 0,
            "failures": 0, "consecutive_successes": 0,
            "base_harness": "tdd-driven",
        }
        assert "exp-harness" in sample_pool["experimental"]

    def test_remove_harness_from_stable(self, full_pool):
        full_pool["stable"].pop("code-review", None)
        assert "code-review" not in full_pool["stable"]

    def test_update_weight_persists(self, sample_pool, tmp_path):
        pool_file = tmp_path / "pool.json"
        sample_pool["stable"]["tdd-driven"]["weight"] = 1.5
        with open(pool_file, "w") as fh:
            json.dump(sample_pool, fh)
        with open(pool_file) as fh:
            loaded = json.load(fh)
        assert loaded["stable"]["tdd-driven"]["weight"] == 1.5

    def test_experimental_entry_has_base_harness(self, sample_pool):
        sample_pool["experimental"]["tdd-driven-v2"] = {
            "weight": 1.0, "total_runs": 0, "successes": 0,
            "failures": 0, "consecutive_successes": 0,
            "base_harness": "tdd-driven",
        }
        assert sample_pool["experimental"]["tdd-driven-v2"]["base_harness"] == "tdd-driven"


# ---------------------------------------------------------------------------
# Bootstrap logic
# ---------------------------------------------------------------------------

class TestBootstrapLogic:
    def test_bootstrap_creates_pool_file(self, tmp_path):
        harnesses_dir = tmp_path / "harnesses"
        harnesses_dir.mkdir()
        (harnesses_dir / "test-harness").mkdir()
        pool_file = str(tmp_path / "pool.json")
        _bootstrap_pool(str(harnesses_dir), pool_file)
        assert os.path.isfile(pool_file)

    def test_bootstrap_discovers_harness_directories(self, tmp_path):
        harnesses_dir = tmp_path / "harnesses"
        harnesses_dir.mkdir()
        (harnesses_dir / "my-harness-a").mkdir()
        (harnesses_dir / "my-harness-b").mkdir()
        pool_file = str(tmp_path / "pool.json")
        pool = _bootstrap_pool(str(harnesses_dir), pool_file)
        assert "my-harness-a" in pool["stable"]
        assert "my-harness-b" in pool["stable"]

    def test_bootstrap_skips_experimental_directory(self, tmp_path):
        harnesses_dir = tmp_path / "harnesses"
        harnesses_dir.mkdir()
        (harnesses_dir / "experimental").mkdir()
        (harnesses_dir / "real-harness").mkdir()
        pool_file = str(tmp_path / "pool.json")
        pool = _bootstrap_pool(str(harnesses_dir), pool_file)
        assert "experimental" not in pool["stable"]
        assert "real-harness" in pool["stable"]

    def test_bootstrap_skips_archived_directory(self, tmp_path):
        harnesses_dir = tmp_path / "harnesses"
        harnesses_dir.mkdir()
        (harnesses_dir / "archived").mkdir()
        (harnesses_dir / "active-harness").mkdir()
        pool_file = str(tmp_path / "pool.json")
        pool = _bootstrap_pool(str(harnesses_dir), pool_file)
        assert "archived" not in pool["stable"]

    def test_bootstrap_skips_shared_directory(self, tmp_path):
        harnesses_dir = tmp_path / "harnesses"
        harnesses_dir.mkdir()
        (harnesses_dir / "_shared").mkdir()
        (harnesses_dir / "normal-harness").mkdir()
        pool_file = str(tmp_path / "pool.json")
        pool = _bootstrap_pool(str(harnesses_dir), pool_file)
        assert "_shared" not in pool["stable"]

    def test_bootstrap_sets_default_weight_1_0(self, tmp_path):
        harnesses_dir = tmp_path / "harnesses"
        harnesses_dir.mkdir()
        (harnesses_dir / "alpha").mkdir()
        pool_file = str(tmp_path / "pool.json")
        pool = _bootstrap_pool(str(harnesses_dir), pool_file)
        assert pool["stable"]["alpha"]["weight"] == 1.0

    def test_bootstrap_sets_zero_counters(self, tmp_path):
        harnesses_dir = tmp_path / "harnesses"
        harnesses_dir.mkdir()
        (harnesses_dir / "beta").mkdir()
        pool_file = str(tmp_path / "pool.json")
        pool = _bootstrap_pool(str(harnesses_dir), pool_file)
        entry = pool["stable"]["beta"]
        assert entry["total_runs"] == 0
        assert entry["successes"] == 0
        assert entry["failures"] == 0
        assert entry["consecutive_successes"] == 0

    def test_bootstrap_plugin_harnesses_match_expected_set(self, tmp_path):
        """Bootstrap against the real plugin harnesses directory."""
        harnesses_dir = os.path.join(PLUGIN_ROOT, "harnesses")
        pool_file = str(tmp_path / "pool.json")
        pool = _bootstrap_pool(harnesses_dir, pool_file)
        for name in STABLE_HARNESS_NAMES:
            assert name in pool["stable"], f"Expected harness '{name}' in bootstrapped pool"

    def test_bootstrap_experimental_pool_is_empty(self, tmp_path):
        harnesses_dir = tmp_path / "harnesses"
        harnesses_dir.mkdir()
        (harnesses_dir / "gamma").mkdir()
        pool_file = str(tmp_path / "pool.json")
        pool = _bootstrap_pool(str(harnesses_dir), pool_file)
        assert pool["experimental"] == {}


# ---------------------------------------------------------------------------
# Pool versioning (serialization round-trip)
# ---------------------------------------------------------------------------

class TestPoolVersioning:
    def test_pool_serializes_to_valid_json(self, full_pool, tmp_path):
        pool_file = tmp_path / "pool.json"
        with open(pool_file, "w") as fh:
            json.dump(full_pool, fh, indent=2)
        with open(pool_file) as fh:
            loaded = json.load(fh)
        assert loaded["stable"] == full_pool["stable"]

    def test_pool_round_trip_preserves_weights(self, full_pool, tmp_path):
        full_pool["stable"]["tdd-driven"]["weight"] = 1.75
        pool_file = tmp_path / "pool.json"
        with open(pool_file, "w") as fh:
            json.dump(full_pool, fh)
        with open(pool_file) as fh:
            loaded = json.load(fh)
        assert loaded["stable"]["tdd-driven"]["weight"] == 1.75

    def test_pool_round_trip_preserves_last_merged_session(self, sample_pool, tmp_path):
        sample_pool["last_merged_session"] = "sess-xyz-123"
        pool_file = tmp_path / "pool.json"
        with open(pool_file, "w") as fh:
            json.dump(sample_pool, fh)
        with open(pool_file) as fh:
            loaded = json.load(fh)
        assert loaded["last_merged_session"] == "sess-xyz-123"
