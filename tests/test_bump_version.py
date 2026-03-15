"""
Tests for scripts/bump_version.py

Behaviors tested:
  1. Rejects invalid semver formats
  2. Accepts valid semver format
  3. Updates plugin.json version field
  4. Updates marketplace.json root version field
  5. Updates marketplace.json plugins[0].version field
  6. Updates CLAUDE.md Current Version line
  7. Prints summary of changes (stdout)
  8. Does not modify files on invalid semver
  9. Idempotent: calling twice with same version is safe
  10. Updates version from non-1.0.x to arbitrary semver
"""

import json
import os
import re
import subprocess
import textwrap

import pytest

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_PATH = os.path.join(WORKSPACE_ROOT, "scripts", "bump_version.py")


def _run_bump(args: list[str], cwd: str = WORKSPACE_ROOT) -> tuple[str, str, int]:
    proc = subprocess.run(
        ["python3", SCRIPT_PATH] + args,
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    return proc.stdout, proc.stderr, proc.returncode


def _make_repo(tmp_path, version: str = "1.0.0") -> dict[str, object]:
    """Create a minimal fake repo structure under tmp_path."""
    plugin_dir = tmp_path / ".claude-plugin"
    plugin_dir.mkdir()

    plugin_json = {
        "name": "adaptive-harness",
        "description": "A test plugin",
        "version": version,
        "author": {"name": "test"},
    }
    (plugin_dir / "plugin.json").write_text(json.dumps(plugin_json, indent=2) + "\n")

    marketplace_json = {
        "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
        "name": "adaptive-harness",
        "plugins": [
            {
                "name": "adaptive-harness",
                "description": "A self-improving harness",
                "version": version,
            }
        ],
        "version": version,
    }
    (plugin_dir / "marketplace.json").write_text(
        json.dumps(marketplace_json, indent=2) + "\n"
    )

    claude_md = textwrap.dedent(f"""\
        # adaptive-harness

        ## Git Workflow

        ### Current Version

        **{version}**
    """)
    (tmp_path / "CLAUDE.md").write_text(claude_md)

    # Also create scripts dir pointing to real script
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()

    return {
        "plugin_json": plugin_dir / "plugin.json",
        "marketplace_json": plugin_dir / "marketplace.json",
        "claude_md": tmp_path / "CLAUDE.md",
    }


# ---------------------------------------------------------------------------
# Behavior 1: Rejects invalid semver formats
# ---------------------------------------------------------------------------

class TestInvalidSemver:
    @pytest.mark.parametrize("bad_version", [
        "1.0",
        "1",
        "v1.0.0",
        "1.0.0-beta",
        "1.0.0.0",
        "abc",
        "",
        "1.x.0",
    ])
    def test_rejects_invalid_semver(self, bad_version):
        stdout, stderr, rc = _run_bump([bad_version])
        assert rc != 0, (
            f"Expected non-zero exit for invalid semver {bad_version!r}. "
            f"stdout={stdout!r}, stderr={stderr!r}"
        )

    @pytest.mark.parametrize("bad_version", ["1.0", "abc", "v1.0.0"])
    def test_error_message_mentions_semver(self, bad_version):
        stdout, stderr, rc = _run_bump([bad_version])
        combined = stdout + stderr
        assert "semver" in combined.lower() or "invalid" in combined.lower(), (
            f"Expected error message for {bad_version!r}. Got: {combined!r}"
        )


# ---------------------------------------------------------------------------
# Behavior 2: Accepts valid semver format
# ---------------------------------------------------------------------------

class TestValidSemver:
    @pytest.mark.parametrize("good_version", [
        "1.0.0",
        "2.3.4",
        "0.0.1",
        "10.20.30",
        "1.2.3",
    ])
    def test_accepts_valid_semver(self, tmp_path, good_version):
        _make_repo(tmp_path, version="1.0.0")
        stdout, stderr, rc = _run_bump([good_version], cwd=str(tmp_path))
        assert rc == 0, (
            f"Expected exit 0 for valid semver {good_version!r}. "
            f"stdout={stdout!r}, stderr={stderr!r}"
        )


# ---------------------------------------------------------------------------
# Behavior 3: Updates plugin.json version field
# ---------------------------------------------------------------------------

class TestUpdatePluginJson:
    def test_updates_plugin_json_version(self, tmp_path):
        files = _make_repo(tmp_path, version="1.0.0")
        stdout, stderr, rc = _run_bump(["2.0.0"], cwd=str(tmp_path))
        assert rc == 0, f"stderr: {stderr}"

        with open(files["plugin_json"]) as fh:
            data = json.load(fh)
        assert data["version"] == "2.0.0", (
            f"Expected plugin.json version='2.0.0'. Got: {data['version']!r}"
        )

    def test_plugin_json_other_fields_preserved(self, tmp_path):
        files = _make_repo(tmp_path, version="1.0.0")
        _run_bump(["1.1.0"], cwd=str(tmp_path))

        with open(files["plugin_json"]) as fh:
            data = json.load(fh)
        assert data["name"] == "adaptive-harness", "name field should be preserved"
        assert "description" in data, "description field should be preserved"


# ---------------------------------------------------------------------------
# Behavior 4 & 5: Updates marketplace.json (root + plugins[0])
# ---------------------------------------------------------------------------

class TestUpdateMarketplaceJson:
    def test_updates_marketplace_root_version(self, tmp_path):
        files = _make_repo(tmp_path, version="1.0.0")
        _run_bump(["2.0.0"], cwd=str(tmp_path))

        with open(files["marketplace_json"]) as fh:
            data = json.load(fh)
        assert data["version"] == "2.0.0", (
            f"Expected marketplace.json root version='2.0.0'. Got: {data['version']!r}"
        )

    def test_updates_marketplace_plugins0_version(self, tmp_path):
        files = _make_repo(tmp_path, version="1.0.0")
        _run_bump(["2.0.0"], cwd=str(tmp_path))

        with open(files["marketplace_json"]) as fh:
            data = json.load(fh)
        assert data["plugins"][0]["version"] == "2.0.0", (
            f"Expected plugins[0].version='2.0.0'. Got: {data['plugins'][0]['version']!r}"
        )

    def test_both_marketplace_versions_updated_together(self, tmp_path):
        files = _make_repo(tmp_path, version="1.0.0")
        _run_bump(["3.1.4"], cwd=str(tmp_path))

        with open(files["marketplace_json"]) as fh:
            data = json.load(fh)
        assert data["version"] == "3.1.4"
        assert data["plugins"][0]["version"] == "3.1.4"

    def test_marketplace_other_fields_preserved(self, tmp_path):
        files = _make_repo(tmp_path, version="1.0.0")
        _run_bump(["1.1.0"], cwd=str(tmp_path))

        with open(files["marketplace_json"]) as fh:
            data = json.load(fh)
        assert data["name"] == "adaptive-harness", "name field should be preserved"
        assert "$schema" in data, "$schema field should be preserved"


# ---------------------------------------------------------------------------
# Behavior 6: Updates CLAUDE.md Current Version line
# ---------------------------------------------------------------------------

class TestUpdateClaudeMd:
    def test_updates_current_version_line(self, tmp_path):
        files = _make_repo(tmp_path, version="1.0.0")
        _run_bump(["2.0.0"], cwd=str(tmp_path))

        content = files["claude_md"].read_text()
        assert "**2.0.0**" in content, (
            f"Expected '**2.0.0**' in CLAUDE.md. Content: {content!r}"
        )

    def test_removes_old_version_from_claude_md(self, tmp_path):
        files = _make_repo(tmp_path, version="1.0.0")
        _run_bump(["2.0.0"], cwd=str(tmp_path))

        content = files["claude_md"].read_text()
        assert "**1.0.0**" not in content, (
            f"Old version '**1.0.0**' should be removed from CLAUDE.md"
        )

    def test_claude_md_other_content_preserved(self, tmp_path):
        files = _make_repo(tmp_path, version="1.0.0")
        _run_bump(["2.0.0"], cwd=str(tmp_path))

        content = files["claude_md"].read_text()
        assert "## Git Workflow" in content, "Other CLAUDE.md sections should be preserved"
        assert "### Current Version" in content, "Section header should be preserved"


# ---------------------------------------------------------------------------
# Behavior 7: Prints summary of changes (stdout)
# ---------------------------------------------------------------------------

class TestSummaryOutput:
    def test_prints_summary_to_stdout(self, tmp_path):
        _make_repo(tmp_path, version="1.0.0")
        stdout, stderr, rc = _run_bump(["2.0.0"], cwd=str(tmp_path))
        assert rc == 0
        assert stdout.strip(), f"Expected non-empty stdout summary. Got: {stdout!r}"

    def test_summary_mentions_new_version(self, tmp_path):
        _make_repo(tmp_path, version="1.0.0")
        stdout, stderr, rc = _run_bump(["2.0.0"], cwd=str(tmp_path))
        assert "2.0.0" in stdout, f"Expected new version in summary. Got: {stdout!r}"

    def test_summary_mentions_plugin_json(self, tmp_path):
        _make_repo(tmp_path, version="1.0.0")
        stdout, stderr, rc = _run_bump(["2.0.0"], cwd=str(tmp_path))
        assert "plugin.json" in stdout or "plugin" in stdout.lower(), (
            f"Expected plugin.json mentioned in summary. Got: {stdout!r}"
        )

    def test_summary_mentions_marketplace_json(self, tmp_path):
        _make_repo(tmp_path, version="1.0.0")
        stdout, stderr, rc = _run_bump(["2.0.0"], cwd=str(tmp_path))
        assert "marketplace" in stdout.lower(), (
            f"Expected marketplace.json mentioned in summary. Got: {stdout!r}"
        )

    def test_summary_mentions_claude_md(self, tmp_path):
        _make_repo(tmp_path, version="1.0.0")
        stdout, stderr, rc = _run_bump(["2.0.0"], cwd=str(tmp_path))
        assert "CLAUDE.md" in stdout or "claude" in stdout.lower(), (
            f"Expected CLAUDE.md mentioned in summary. Got: {stdout!r}"
        )


# ---------------------------------------------------------------------------
# Behavior 8: Does not modify files on invalid semver
# ---------------------------------------------------------------------------

class TestNoModificationOnError:
    def test_plugin_json_not_modified_on_invalid_version(self, tmp_path):
        files = _make_repo(tmp_path, version="1.0.0")
        mtime_before = files["plugin_json"].stat().st_mtime
        _run_bump(["invalid"], cwd=str(tmp_path))
        mtime_after = files["plugin_json"].stat().st_mtime
        assert mtime_before == mtime_after, "plugin.json should not be modified on invalid semver"

    def test_marketplace_json_not_modified_on_invalid_version(self, tmp_path):
        files = _make_repo(tmp_path, version="1.0.0")
        mtime_before = files["marketplace_json"].stat().st_mtime
        _run_bump(["v2.0"], cwd=str(tmp_path))
        mtime_after = files["marketplace_json"].stat().st_mtime
        assert mtime_before == mtime_after, "marketplace.json should not be modified on invalid semver"

    def test_claude_md_not_modified_on_invalid_version(self, tmp_path):
        files = _make_repo(tmp_path, version="1.0.0")
        mtime_before = files["claude_md"].stat().st_mtime
        _run_bump(["not-a-version"], cwd=str(tmp_path))
        mtime_after = files["claude_md"].stat().st_mtime
        assert mtime_before == mtime_after, "CLAUDE.md should not be modified on invalid semver"


# ---------------------------------------------------------------------------
# Behavior 9: Idempotent — calling twice with same version is safe
# ---------------------------------------------------------------------------

class TestIdempotency:
    def test_running_twice_with_same_version_is_safe(self, tmp_path):
        files = _make_repo(tmp_path, version="1.0.0")
        _run_bump(["2.0.0"], cwd=str(tmp_path))
        stdout2, stderr2, rc2 = _run_bump(["2.0.0"], cwd=str(tmp_path))
        assert rc2 == 0, f"Second run with same version failed: {stderr2}"

        with open(files["plugin_json"]) as fh:
            data = json.load(fh)
        assert data["version"] == "2.0.0", "Version should still be 2.0.0 after second run"

    def test_running_twice_marketplace_still_correct(self, tmp_path):
        files = _make_repo(tmp_path, version="1.0.0")
        _run_bump(["2.0.0"], cwd=str(tmp_path))
        _run_bump(["2.0.0"], cwd=str(tmp_path))

        with open(files["marketplace_json"]) as fh:
            data = json.load(fh)
        assert data["version"] == "2.0.0"
        assert data["plugins"][0]["version"] == "2.0.0"


# ---------------------------------------------------------------------------
# Behavior 10: Updates version from non-1.0.x to arbitrary semver
# ---------------------------------------------------------------------------

class TestArbitrarySemver:
    def test_bump_major_version(self, tmp_path):
        files = _make_repo(tmp_path, version="0.5.3")
        _run_bump(["10.0.0"], cwd=str(tmp_path))

        with open(files["plugin_json"]) as fh:
            data = json.load(fh)
        assert data["version"] == "10.0.0"

    def test_bump_patch_version(self, tmp_path):
        files = _make_repo(tmp_path, version="2.3.4")
        _run_bump(["2.3.5"], cwd=str(tmp_path))

        with open(files["plugin_json"]) as fh:
            data = json.load(fh)
        assert data["version"] == "2.3.5"

    def test_no_version_argument_exits_with_error(self):
        stdout, stderr, rc = _run_bump([])
        assert rc != 0, "Expected non-zero exit when no version argument provided"
