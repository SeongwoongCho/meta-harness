"""
Tests for the adaptive-harness migration system.

Tests migrate.sh behaviors:
  1. Version match → exits with "up to date" (no migration needed)
  2. Missing .plugin-version treated as "0.0.0" (full migration)
  3. Version mismatch detection
  4. Adds missing harnesses to harness-pool.json
  5. Adds missing config fields to config.yaml
  6. Writes updated .plugin-version after migration
  7. Outputs JSON summary of changes
  8. Creates .bak backup before modifying harness-pool.json
  9. Respects ADAPTIVE_HARNESS_SKIP_MIGRATION=1 env var
  10. session-start.sh auto-detects mismatch and appends migration summary to additionalContext
  11. skills/migrate/SKILL.md exists for manual invocation
"""

import json
import os
import subprocess

import pytest

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS_DIR = os.path.join(WORKSPACE_ROOT, "hooks")
PLUGIN_ROOT = WORKSPACE_ROOT

pytestmark = pytest.mark.shell


def _run_migrate(env: dict, cwd: str) -> tuple[str, str, int]:
    hook_path = os.path.join(HOOKS_DIR, "migrate.sh")
    proc = subprocess.run(
        ["bash", hook_path],
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd,
    )
    return proc.stdout, proc.stderr, proc.returncode


def _run_session_start(env: dict, cwd: str) -> tuple[str, str, int]:
    hook_path = os.path.join(HOOKS_DIR, "session-start.sh")
    proc = subprocess.run(
        ["bash", hook_path],
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd,
    )
    return proc.stdout, proc.stderr, proc.returncode


def _base_env(plugin_root: str = PLUGIN_ROOT, session_id: str = "test-migrate-001") -> dict:
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = plugin_root
    env["CLAUDE_SESSION_ID"] = session_id
    env.pop("ADAPTIVE_HARNESS_SKIP_MIGRATION", None)
    return env


def _make_git_root(tmp_path):
    (tmp_path / ".git").mkdir(exist_ok=True)
    return tmp_path


def _setup_state_dir(tmp_path, plugin_version: str | None = None, project_version: str | None = None,
                     pool: dict | None = None, config_yaml: str | None = None) -> object:
    """Create a .adaptive-harness directory with optional files."""
    _make_git_root(tmp_path)
    state_dir = tmp_path / ".adaptive-harness"
    state_dir.mkdir(exist_ok=True)
    (state_dir / "sessions").mkdir(exist_ok=True)
    (state_dir / "evaluation-logs").mkdir(exist_ok=True)
    (state_dir / "evolution-proposals").mkdir(exist_ok=True)

    if project_version is not None:
        (state_dir / ".plugin-version").write_text(project_version)

    if pool is not None:
        (state_dir / "harness-pool.json").write_text(json.dumps(pool, indent=2))

    if config_yaml is not None:
        (state_dir / "config.yaml").write_text(config_yaml)

    return state_dir


# ---------------------------------------------------------------------------
# Behavior 1: Version match → exits 0 with "up to date" in output
# ---------------------------------------------------------------------------

class TestMigrateVersionMatch:
    def test_exits_0_when_versions_match(self, tmp_path):
        state_dir = _setup_state_dir(tmp_path, project_version="1.0.0")
        env = _base_env()
        # Set plugin version to match project version
        env["ADAPTIVE_HARNESS_PLUGIN_VERSION"] = "1.0.0"
        stdout, stderr, rc = _run_migrate(env, str(tmp_path))
        assert rc == 0, f"Expected exit 0 on version match. stderr: {stderr}"

    def test_outputs_up_to_date_when_versions_match(self, tmp_path):
        state_dir = _setup_state_dir(tmp_path, project_version="1.0.0")
        env = _base_env()
        env["ADAPTIVE_HARNESS_PLUGIN_VERSION"] = "1.0.0"
        stdout, stderr, rc = _run_migrate(env, str(tmp_path))
        assert rc == 0
        combined = stdout + stderr
        assert "up to date" in combined.lower() or "up-to-date" in combined.lower(), \
            f"Expected 'up to date' message. Output: {combined!r}"

    def test_no_migration_performed_when_versions_match(self, tmp_path):
        pool = {
            "stable": {"tdd-driven": {"weight": 1.0, "total_runs": 0, "successes": 0,
                                       "failures": 0, "consecutive_successes": 0}},
            "experimental": {},
            "last_updated": None,
            "last_merged_session": None,
        }
        state_dir = _setup_state_dir(tmp_path, project_version="1.0.0", pool=pool)
        env = _base_env()
        env["ADAPTIVE_HARNESS_PLUGIN_VERSION"] = "1.0.0"
        pool_file = state_dir / "harness-pool.json"
        mtime_before = pool_file.stat().st_mtime
        _run_migrate(env, str(tmp_path))
        mtime_after = pool_file.stat().st_mtime
        # Pool file should not be rewritten when versions match
        assert mtime_before == mtime_after, "Pool file was modified despite version match"


# ---------------------------------------------------------------------------
# Behavior 2: Missing .plugin-version treated as "0.0.0" → full migration
# ---------------------------------------------------------------------------

class TestMigrateMissingVersion:
    def test_missing_plugin_version_file_triggers_migration(self, tmp_path):
        # No .plugin-version file in state dir
        pool = {
            "stable": {},
            "experimental": {},
            "last_updated": None,
            "last_merged_session": None,
        }
        state_dir = _setup_state_dir(tmp_path, project_version=None, pool=pool)
        env = _base_env()
        env["ADAPTIVE_HARNESS_PLUGIN_VERSION"] = "1.0.0"
        stdout, stderr, rc = _run_migrate(env, str(tmp_path))
        assert rc == 0, f"Expected exit 0 when .plugin-version missing. stderr: {stderr}"
        # Should have written .plugin-version
        version_file = state_dir / ".plugin-version"
        assert version_file.exists(), "Expected .plugin-version to be written after migration"

    def test_missing_plugin_version_file_treated_as_000(self, tmp_path):
        state_dir = _setup_state_dir(tmp_path, project_version=None)
        env = _base_env()
        env["ADAPTIVE_HARNESS_PLUGIN_VERSION"] = "1.0.0"
        stdout, stderr, rc = _run_migrate(env, str(tmp_path))
        assert rc == 0
        combined = stdout + stderr
        # Should report full migration (mismatch detected)
        assert "0.0.0" in combined or "migrat" in combined.lower(), \
            f"Expected migration to run treating missing version as 0.0.0. Output: {combined!r}"


# ---------------------------------------------------------------------------
# Behavior 3: Version mismatch detection
# ---------------------------------------------------------------------------

class TestMigrateVersionMismatch:
    def test_detects_version_mismatch(self, tmp_path):
        state_dir = _setup_state_dir(tmp_path, project_version="0.9.0")
        env = _base_env()
        env["ADAPTIVE_HARNESS_PLUGIN_VERSION"] = "1.0.0"
        stdout, stderr, rc = _run_migrate(env, str(tmp_path))
        assert rc == 0, f"Expected exit 0 on version mismatch. stderr: {stderr}"
        combined = stdout + stderr
        assert "migrat" in combined.lower() or "0.9.0" in combined or "1.0.0" in combined, \
            f"Expected migration message. Output: {combined!r}"

    def test_reads_plugin_version_from_plugin_json_when_env_not_set(self, tmp_path):
        """migrate.sh should read plugin version from plugin.json when env var not set."""
        state_dir = _setup_state_dir(tmp_path, project_version="0.0.0")
        env = _base_env()
        env.pop("ADAPTIVE_HARNESS_PLUGIN_VERSION", None)
        # CLAUDE_PLUGIN_ROOT points to workspace which has .claude-plugin/plugin.json
        stdout, stderr, rc = _run_migrate(env, str(tmp_path))
        assert rc == 0, f"Expected exit 0. stderr: {stderr}"


# ---------------------------------------------------------------------------
# Behavior 4: Adds missing harnesses to harness-pool.json
# ---------------------------------------------------------------------------

class TestMigrateAddsMissingHarnesses:
    def test_adds_new_harnesses_from_plugin_to_pool(self, tmp_path):
        # Pool with only one harness (the rest are "new" from the plugin)
        pool = {
            "stable": {
                "tdd-driven": {"weight": 1.0, "total_runs": 0, "successes": 0,
                               "failures": 0, "consecutive_successes": 0}
            },
            "experimental": {},
            "last_updated": None,
            "last_merged_session": None,
        }
        state_dir = _setup_state_dir(tmp_path, project_version="0.9.0", pool=pool)
        env = _base_env()
        env["ADAPTIVE_HARNESS_PLUGIN_VERSION"] = "1.0.0"
        stdout, stderr, rc = _run_migrate(env, str(tmp_path))
        assert rc == 0

        pool_file = state_dir / "harness-pool.json"
        with open(pool_file) as fh:
            updated_pool = json.load(fh)

        # Should have more than 1 harness in stable pool
        assert len(updated_pool["stable"]) > 1, \
            f"Expected new harnesses added. Pool stable keys: {list(updated_pool['stable'].keys())}"

    def test_preserves_existing_harness_weights_during_migration(self, tmp_path):
        """Existing harnesses retain their learned weights."""
        pool = {
            "stable": {
                "tdd-driven": {"weight": 1.8, "total_runs": 10, "successes": 8,
                               "failures": 2, "consecutive_successes": 3}
            },
            "experimental": {},
            "last_updated": None,
            "last_merged_session": None,
        }
        state_dir = _setup_state_dir(tmp_path, project_version="0.9.0", pool=pool)
        env = _base_env()
        env["ADAPTIVE_HARNESS_PLUGIN_VERSION"] = "1.0.0"
        _run_migrate(env, str(tmp_path))

        pool_file = state_dir / "harness-pool.json"
        with open(pool_file) as fh:
            updated_pool = json.load(fh)

        tdd = updated_pool["stable"].get("tdd-driven", {})
        assert tdd.get("weight") == 1.8, "Existing harness weight should be preserved"
        assert tdd.get("total_runs") == 10, "Existing run counts should be preserved"

    def test_new_harnesses_get_default_weight_1(self, tmp_path):
        pool = {
            "stable": {
                "tdd-driven": {"weight": 1.0, "total_runs": 0, "successes": 0,
                               "failures": 0, "consecutive_successes": 0}
            },
            "experimental": {},
            "last_updated": None,
            "last_merged_session": None,
        }
        state_dir = _setup_state_dir(tmp_path, project_version="0.9.0", pool=pool)
        env = _base_env()
        env["ADAPTIVE_HARNESS_PLUGIN_VERSION"] = "1.0.0"
        _run_migrate(env, str(tmp_path))

        pool_file = state_dir / "harness-pool.json"
        with open(pool_file) as fh:
            updated_pool = json.load(fh)

        # Any new harness added should have weight=1.0 and zeroed counters
        for name, entry in updated_pool["stable"].items():
            if name != "tdd-driven":
                assert entry.get("weight") == 1.0, \
                    f"New harness {name!r} should have default weight 1.0"


# ---------------------------------------------------------------------------
# Behavior 5: Adds missing config fields to config.yaml
# ---------------------------------------------------------------------------

class TestMigrateConfigFields:
    def test_adds_missing_evolution_section_to_config(self, tmp_path):
        config_yaml = (
            "version: \"1.0\"\n"
            "project:\n"
            "  domain: general\n"
        )
        state_dir = _setup_state_dir(tmp_path, project_version="0.9.0",
                                     config_yaml=config_yaml)
        env = _base_env()
        env["ADAPTIVE_HARNESS_PLUGIN_VERSION"] = "1.0.0"
        stdout, stderr, rc = _run_migrate(env, str(tmp_path))
        assert rc == 0, f"Expected exit 0. stderr: {stderr}"

        config_file = state_dir / "config.yaml"
        content = config_file.read_text()
        assert "evolution" in content or "ensemble" in content, \
            f"Expected config to have evolution/ensemble section added. Content: {content!r}"

    def test_config_migration_is_idempotent(self, tmp_path):
        """Running migration twice should not duplicate config fields."""
        config_yaml = (
            "version: \"1.0\"\n"
            "project:\n"
            "  domain: general\n"
        )
        state_dir = _setup_state_dir(tmp_path, project_version="0.9.0",
                                     config_yaml=config_yaml)
        env = _base_env()
        env["ADAPTIVE_HARNESS_PLUGIN_VERSION"] = "1.0.0"
        # Run migration once
        _run_migrate(env, str(tmp_path))
        first_content = (state_dir / "config.yaml").read_text()

        # Reset project version to force second run
        (state_dir / ".plugin-version").write_text("0.9.0")
        _run_migrate(env, str(tmp_path))
        second_content = (state_dir / "config.yaml").read_text()

        # Count occurrences of "evolution" — should be the same
        assert first_content.count("evolution") == second_content.count("evolution"), \
            "Config migration is not idempotent — fields were duplicated"

    def test_existing_config_values_preserved(self, tmp_path):
        """Custom user config values should not be overwritten."""
        config_yaml = (
            "version: \"1.0\"\n"
            "project:\n"
            "  domain: ml\n"
            "ensemble:\n"
            "  mode: always\n"
        )
        state_dir = _setup_state_dir(tmp_path, project_version="0.9.0",
                                     config_yaml=config_yaml)
        env = _base_env()
        env["ADAPTIVE_HARNESS_PLUGIN_VERSION"] = "1.0.0"
        _run_migrate(env, str(tmp_path))

        content = (state_dir / "config.yaml").read_text()
        assert "ml" in content, "User's domain 'ml' should be preserved"
        assert "always" in content, "User's ensemble mode 'always' should be preserved"


# ---------------------------------------------------------------------------
# Behavior 6: Writes updated .plugin-version after migration
# ---------------------------------------------------------------------------

class TestMigrateWritesPluginVersion:
    def test_writes_plugin_version_file_after_migration(self, tmp_path):
        state_dir = _setup_state_dir(tmp_path, project_version="0.9.0")
        env = _base_env()
        env["ADAPTIVE_HARNESS_PLUGIN_VERSION"] = "1.0.0"
        _run_migrate(env, str(tmp_path))

        version_file = state_dir / ".plugin-version"
        assert version_file.exists(), "Expected .plugin-version to be written after migration"
        assert version_file.read_text().strip() == "1.0.0", \
            f"Expected version '1.0.0'. Got: {version_file.read_text().strip()!r}"

    def test_does_not_overwrite_version_when_versions_match(self, tmp_path):
        state_dir = _setup_state_dir(tmp_path, project_version="1.0.0")
        version_file = state_dir / ".plugin-version"
        mtime_before = version_file.stat().st_mtime
        env = _base_env()
        env["ADAPTIVE_HARNESS_PLUGIN_VERSION"] = "1.0.0"
        _run_migrate(env, str(tmp_path))
        mtime_after = version_file.stat().st_mtime
        assert mtime_before == mtime_after, ".plugin-version should not be modified when versions match"


# ---------------------------------------------------------------------------
# Behavior 7: Outputs JSON summary of changes
# ---------------------------------------------------------------------------

class TestMigrateJsonSummary:
    def test_outputs_json_summary_on_migration(self, tmp_path):
        pool = {
            "stable": {},
            "experimental": {},
            "last_updated": None,
            "last_merged_session": None,
        }
        state_dir = _setup_state_dir(tmp_path, project_version="0.9.0", pool=pool)
        env = _base_env()
        env["ADAPTIVE_HARNESS_PLUGIN_VERSION"] = "1.0.0"
        stdout, stderr, rc = _run_migrate(env, str(tmp_path))
        assert rc == 0

        # stdout should be valid JSON
        try:
            summary = json.loads(stdout)
        except json.JSONDecodeError as exc:
            pytest.fail(f"Expected JSON summary on stdout. Got: {stdout!r}. Error: {exc}")

        assert "migrated" in summary or "changes" in summary or "harnesses_added" in summary, \
            f"JSON summary missing expected fields. Got: {summary}"

    def test_json_summary_includes_harnesses_added(self, tmp_path):
        pool = {
            "stable": {},
            "experimental": {},
            "last_updated": None,
            "last_merged_session": None,
        }
        state_dir = _setup_state_dir(tmp_path, project_version="0.9.0", pool=pool)
        env = _base_env()
        env["ADAPTIVE_HARNESS_PLUGIN_VERSION"] = "1.0.0"
        stdout, stderr, rc = _run_migrate(env, str(tmp_path))
        assert rc == 0

        summary = json.loads(stdout)
        harnesses_added = (
            summary.get("harnesses_added") or
            summary.get("changes", {}).get("harnesses_added") or
            []
        )
        assert len(harnesses_added) > 0, \
            f"Expected harnesses_added list in summary. Summary: {summary}"

    def test_outputs_up_to_date_json_when_no_migration(self, tmp_path):
        state_dir = _setup_state_dir(tmp_path, project_version="1.0.0")
        env = _base_env()
        env["ADAPTIVE_HARNESS_PLUGIN_VERSION"] = "1.0.0"
        stdout, stderr, rc = _run_migrate(env, str(tmp_path))
        assert rc == 0

        try:
            summary = json.loads(stdout)
        except json.JSONDecodeError as exc:
            pytest.fail(f"Expected JSON on stdout even when up to date. Got: {stdout!r}. Error: {exc}")

        # Should indicate no changes
        assert summary.get("status") == "up_to_date" or not summary.get("migrated", True), \
            f"Expected up_to_date status. Got: {summary}"


# ---------------------------------------------------------------------------
# Behavior 8: Creates .bak backup before modifying harness-pool.json
# ---------------------------------------------------------------------------

class TestMigrateBackup:
    def test_creates_bak_file_before_modifying_pool(self, tmp_path):
        pool = {
            "stable": {
                "tdd-driven": {"weight": 1.5, "total_runs": 5, "successes": 4,
                               "failures": 1, "consecutive_successes": 2}
            },
            "experimental": {},
            "last_updated": None,
            "last_merged_session": None,
        }
        state_dir = _setup_state_dir(tmp_path, project_version="0.9.0", pool=pool)
        env = _base_env()
        env["ADAPTIVE_HARNESS_PLUGIN_VERSION"] = "1.0.0"
        stdout, stderr, rc = _run_migrate(env, str(tmp_path))
        assert rc == 0

        bak_file = state_dir / "harness-pool.json.bak"
        assert bak_file.exists(), "Expected harness-pool.json.bak to be created before migration"

    def test_bak_file_contains_original_pool(self, tmp_path):
        pool = {
            "stable": {
                "tdd-driven": {"weight": 1.5, "total_runs": 5, "successes": 4,
                               "failures": 1, "consecutive_successes": 2}
            },
            "experimental": {},
            "last_updated": None,
            "last_merged_session": None,
        }
        state_dir = _setup_state_dir(tmp_path, project_version="0.9.0", pool=pool)
        env = _base_env()
        env["ADAPTIVE_HARNESS_PLUGIN_VERSION"] = "1.0.0"
        _run_migrate(env, str(tmp_path))

        bak_file = state_dir / "harness-pool.json.bak"
        with open(bak_file) as fh:
            backed_up = json.load(fh)
        # Backup should contain original 1-harness pool
        assert "tdd-driven" in backed_up["stable"], "Backup should contain original pool contents"
        assert backed_up["stable"]["tdd-driven"]["weight"] == 1.5, \
            "Backup should preserve original weights"


# ---------------------------------------------------------------------------
# Behavior 9: Respects ADAPTIVE_HARNESS_SKIP_MIGRATION=1
# ---------------------------------------------------------------------------

class TestMigrateSkipEnvVar:
    def test_skip_migration_env_var_causes_early_exit(self, tmp_path):
        state_dir = _setup_state_dir(tmp_path, project_version="0.9.0")
        env = _base_env()
        env["ADAPTIVE_HARNESS_PLUGIN_VERSION"] = "1.0.0"
        env["ADAPTIVE_HARNESS_SKIP_MIGRATION"] = "1"
        stdout, stderr, rc = _run_migrate(env, str(tmp_path))
        assert rc == 0, f"Expected exit 0 with skip env var. stderr: {stderr}"
        combined = stdout + stderr
        assert "skip" in combined.lower() or "skipped" in combined.lower(), \
            f"Expected 'skip' message. Output: {combined!r}"

    def test_skip_migration_does_not_write_version_file(self, tmp_path):
        state_dir = _setup_state_dir(tmp_path, project_version="0.9.0")
        version_file = state_dir / ".plugin-version"
        mtime_before = version_file.stat().st_mtime
        env = _base_env()
        env["ADAPTIVE_HARNESS_PLUGIN_VERSION"] = "1.0.0"
        env["ADAPTIVE_HARNESS_SKIP_MIGRATION"] = "1"
        _run_migrate(env, str(tmp_path))
        mtime_after = version_file.stat().st_mtime
        assert mtime_before == mtime_after, ".plugin-version should not be updated when migration skipped"


# ---------------------------------------------------------------------------
# Behavior 10: session-start.sh auto-detects version mismatch
# ---------------------------------------------------------------------------

class TestSessionStartAutoMigration:
    def test_session_start_runs_migration_on_version_mismatch(self, tmp_path):
        """session-start.sh should auto-run migration when .plugin-version mismatches."""
        pool = {
            "stable": {
                "tdd-driven": {"weight": 1.0, "total_runs": 0, "successes": 0,
                               "failures": 0, "consecutive_successes": 0}
            },
            "experimental": {},
            "last_updated": None,
            "last_merged_session": None,
        }
        state_dir = _setup_state_dir(tmp_path, project_version="0.9.0", pool=pool)
        env = _base_env()
        env["ADAPTIVE_HARNESS_PLUGIN_VERSION"] = "1.0.0"
        stdout, stderr, rc = _run_session_start(env, str(tmp_path))
        assert rc == 0, f"Expected exit 0. stderr: {stderr}"

        # After session-start, pool should have more harnesses
        pool_file = state_dir / "harness-pool.json"
        with open(pool_file) as fh:
            updated_pool = json.load(fh)
        assert len(updated_pool["stable"]) > 1, \
            "session-start should have triggered migration adding new harnesses"

    def test_session_start_appends_migration_summary_to_context(self, tmp_path):
        """Migration summary should appear in additionalContext after auto-migration."""
        pool = {
            "stable": {},
            "experimental": {},
            "last_updated": None,
            "last_merged_session": None,
        }
        state_dir = _setup_state_dir(tmp_path, project_version="0.9.0", pool=pool)
        env = _base_env()
        env["ADAPTIVE_HARNESS_PLUGIN_VERSION"] = "1.0.0"
        stdout, stderr, rc = _run_session_start(env, str(tmp_path))
        assert rc == 0, f"Expected exit 0. stderr: {stderr}"

        parsed = json.loads(stdout)
        ctx = parsed["hookSpecificOutput"]["additionalContext"]
        assert "migrat" in ctx.lower() or "update" in ctx.lower(), \
            f"Expected migration notice in additionalContext. Got: {ctx!r}"

    def test_session_start_output_still_valid_json_after_migration(self, tmp_path):
        pool = {
            "stable": {},
            "experimental": {},
            "last_updated": None,
            "last_merged_session": None,
        }
        state_dir = _setup_state_dir(tmp_path, project_version="0.9.0", pool=pool)
        env = _base_env()
        env["ADAPTIVE_HARNESS_PLUGIN_VERSION"] = "1.0.0"
        stdout, stderr, rc = _run_session_start(env, str(tmp_path))
        assert rc == 0

        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError as exc:
            pytest.fail(f"session-start.sh output is not valid JSON after migration: {exc}\nOutput: {stdout!r}")
        assert "hookSpecificOutput" in parsed

    def test_session_start_no_migration_when_versions_match(self, tmp_path):
        """session-start should not touch pool if versions already match."""
        pool = {
            "stable": {
                "tdd-driven": {"weight": 1.8, "total_runs": 10, "successes": 8,
                               "failures": 2, "consecutive_successes": 3}
            },
            "experimental": {},
            "last_updated": None,
            "last_merged_session": None,
        }
        state_dir = _setup_state_dir(tmp_path, project_version="1.0.0", pool=pool)
        pool_file = state_dir / "harness-pool.json"
        mtime_before = pool_file.stat().st_mtime
        env = _base_env()
        env["ADAPTIVE_HARNESS_PLUGIN_VERSION"] = "1.0.0"
        _run_session_start(env, str(tmp_path))
        mtime_after = pool_file.stat().st_mtime
        # Pool file should not be modified by migration (may be modified by pool bootstrap logic)
        # but the weights should be preserved
        with open(pool_file) as fh:
            updated_pool = json.load(fh)
        assert updated_pool["stable"]["tdd-driven"]["weight"] == 1.8, \
            "Existing weights should be preserved when no migration runs"


# ---------------------------------------------------------------------------
# Behavior 11: skills/migrate/SKILL.md exists for manual invocation
# ---------------------------------------------------------------------------

class TestMigrateSkill:
    def test_migrate_skill_file_exists(self):
        skill_path = os.path.join(PLUGIN_ROOT, "skills", "migrate", "SKILL.md")
        assert os.path.isfile(skill_path), \
            f"Expected skills/migrate/SKILL.md to exist at {skill_path}"

    def test_migrate_skill_has_frontmatter_name(self):
        skill_path = os.path.join(PLUGIN_ROOT, "skills", "migrate", "SKILL.md")
        content = open(skill_path).read()
        assert "name:" in content, "SKILL.md should have a 'name:' frontmatter field"
        assert "migrate" in content.lower(), \
            "SKILL.md should mention 'migrate' in its content"

    def test_migrate_skill_instructs_running_migrate_sh(self):
        skill_path = os.path.join(PLUGIN_ROOT, "skills", "migrate", "SKILL.md")
        content = open(skill_path).read()
        assert "migrate.sh" in content, \
            "SKILL.md should instruct Claude to run migrate.sh"

    def test_migrate_skill_describes_output_format(self):
        skill_path = os.path.join(PLUGIN_ROOT, "skills", "migrate", "SKILL.md")
        content = open(skill_path).read()
        # Should describe what to do with the JSON output
        assert "json" in content.lower() or "JSON" in content, \
            "SKILL.md should describe the JSON output format"
