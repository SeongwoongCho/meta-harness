"""
Tests for the 5 new harnesses:
  deep-interview, simple-executor, documentation-writer, security-audit, performance-optimization

RED phase: these tests must fail before implementation, pass after.
"""

import json
import os

import pytest

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HARNESSES_DIR = os.path.join(WORKSPACE_ROOT, "harnesses")
AGENTS_DIR = os.path.join(WORKSPACE_ROOT, "agents")
POOL_FILE = os.path.join(WORKSPACE_ROOT, ".adaptive-harness", "harness-pool.json")

NEW_HARNESS_NAMES = [
    "deep-interview",
    "simple-executor",
    "documentation-writer",
    "security-audit",
    "performance-optimization",
]

REQUIRED_HARNESS_FILES = ["skill.md", "contract.yaml", "metadata.json"]


# ---------------------------------------------------------------------------
# Harness directory structure
# ---------------------------------------------------------------------------

class TestNewHarnessDirectories:
    @pytest.mark.parametrize("name", NEW_HARNESS_NAMES)
    def test_harness_directory_exists(self, name):
        path = os.path.join(HARNESSES_DIR, name)
        assert os.path.isdir(path), f"Directory missing: {path}"

    @pytest.mark.parametrize("name", NEW_HARNESS_NAMES)
    @pytest.mark.parametrize("filename", REQUIRED_HARNESS_FILES)
    def test_harness_has_required_file(self, name, filename):
        path = os.path.join(HARNESSES_DIR, name, filename)
        assert os.path.isfile(path), f"File missing: {path}"

    @pytest.mark.parametrize("name", NEW_HARNESS_NAMES)
    def test_harness_skill_md_not_empty(self, name):
        path = os.path.join(HARNESSES_DIR, name, "skill.md")
        with open(path) as fh:
            content = fh.read()
        assert len(content.strip()) > 0, f"skill.md is empty: {path}"

    @pytest.mark.parametrize("name", NEW_HARNESS_NAMES)
    def test_harness_contract_yaml_not_empty(self, name):
        path = os.path.join(HARNESSES_DIR, name, "contract.yaml")
        with open(path) as fh:
            content = fh.read()
        assert len(content.strip()) > 0, f"contract.yaml is empty: {path}"

    @pytest.mark.parametrize("name", NEW_HARNESS_NAMES)
    def test_harness_metadata_json_is_valid(self, name):
        path = os.path.join(HARNESSES_DIR, name, "metadata.json")
        with open(path) as fh:
            data = json.load(fh)
        assert isinstance(data, dict), f"metadata.json is not a dict: {path}"

    @pytest.mark.parametrize("name", NEW_HARNESS_NAMES)
    def test_harness_metadata_has_required_fields(self, name):
        path = os.path.join(HARNESSES_DIR, name, "metadata.json")
        with open(path) as fh:
            data = json.load(fh)
        for field in ("pool", "weight"):
            assert field in data, f"metadata.json missing '{field}': {path}"

    @pytest.mark.parametrize("name", NEW_HARNESS_NAMES)
    def test_harness_metadata_pool_is_stable(self, name):
        path = os.path.join(HARNESSES_DIR, name, "metadata.json")
        with open(path) as fh:
            data = json.load(fh)
        assert data["pool"] == "stable", f"Expected pool=stable in {path}"

    @pytest.mark.parametrize("name", NEW_HARNESS_NAMES)
    def test_harness_metadata_weight_is_1_0(self, name):
        path = os.path.join(HARNESSES_DIR, name, "metadata.json")
        with open(path) as fh:
            data = json.load(fh)
        assert data["weight"] == 1.0, f"Expected weight=1.0 in {path}"

    @pytest.mark.parametrize("name", NEW_HARNESS_NAMES)
    def test_contract_yaml_has_name_field(self, name):
        """Contract should start with 'name: <harness-name>'."""
        path = os.path.join(HARNESSES_DIR, name, "contract.yaml")
        with open(path) as fh:
            content = fh.read()
        assert f"name: {name}" in content, f"contract.yaml missing 'name: {name}' in {path}"

    @pytest.mark.parametrize("name", NEW_HARNESS_NAMES)
    def test_contract_yaml_has_trigger_section(self, name):
        path = os.path.join(HARNESSES_DIR, name, "contract.yaml")
        with open(path) as fh:
            content = fh.read()
        assert "trigger:" in content, f"contract.yaml missing 'trigger:' in {path}"

    @pytest.mark.parametrize("name", NEW_HARNESS_NAMES)
    def test_contract_yaml_has_workflow_section(self, name):
        path = os.path.join(HARNESSES_DIR, name, "contract.yaml")
        with open(path) as fh:
            content = fh.read()
        assert "workflow:" in content, f"contract.yaml missing 'workflow:' in {path}"


# ---------------------------------------------------------------------------
# Agent files
# ---------------------------------------------------------------------------

class TestNewHarnessAgents:
    @pytest.mark.parametrize("name", NEW_HARNESS_NAMES)
    def test_agent_file_exists(self, name):
        path = os.path.join(AGENTS_DIR, f"{name}.md")
        assert os.path.isfile(path), f"Agent file missing: {path}"

    @pytest.mark.parametrize("name", NEW_HARNESS_NAMES)
    def test_agent_file_not_empty(self, name):
        path = os.path.join(AGENTS_DIR, f"{name}.md")
        with open(path) as fh:
            content = fh.read()
        assert len(content.strip()) > 0, f"Agent file is empty: {path}"

    @pytest.mark.parametrize("name", NEW_HARNESS_NAMES)
    def test_agent_file_has_frontmatter(self, name):
        """Agent files must start with YAML front-matter delimited by ---."""
        path = os.path.join(AGENTS_DIR, f"{name}.md")
        with open(path) as fh:
            content = fh.read()
        assert content.startswith("---"), f"Agent file missing front-matter: {path}"

    @pytest.mark.parametrize("name", NEW_HARNESS_NAMES)
    def test_agent_file_has_name_in_frontmatter(self, name):
        path = os.path.join(AGENTS_DIR, f"{name}.md")
        with open(path) as fh:
            content = fh.read()
        assert f"name: {name}" in content, f"Agent file missing 'name: {name}': {path}"

    @pytest.mark.parametrize("name", NEW_HARNESS_NAMES)
    def test_agent_file_has_model_in_frontmatter(self, name):
        path = os.path.join(AGENTS_DIR, f"{name}.md")
        with open(path) as fh:
            content = fh.read()
        assert "model:" in content, f"Agent file missing 'model:' in front-matter: {path}"


# ---------------------------------------------------------------------------
# Harness pool registration
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not os.path.isfile(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".adaptive-harness", "harness-pool.json")),
    reason="harness-pool.json is a runtime file (gitignored); not available in CI",
)
class TestNewHarnessPoolRegistration:
    def _load_pool(self):
        with open(POOL_FILE) as fh:
            return json.load(fh)

    @pytest.mark.parametrize("name", NEW_HARNESS_NAMES)
    def test_new_harness_in_pool_stable(self, name):
        pool = self._load_pool()
        assert name in pool["stable"], f"Harness '{name}' not found in pool stable"

    @pytest.mark.parametrize("name", NEW_HARNESS_NAMES)
    def test_new_harness_pool_weight_is_1_0(self, name):
        pool = self._load_pool()
        assert pool["stable"][name]["weight"] == 1.0, f"Weight != 1.0 for {name}"

    @pytest.mark.parametrize("name", NEW_HARNESS_NAMES)
    def test_new_harness_pool_has_required_fields(self, name):
        pool = self._load_pool()
        entry = pool["stable"][name]
        for field in ("weight", "total_runs", "successes", "failures", "consecutive_successes"):
            assert field in entry, f"Missing field '{field}' for {name} in pool"


# ---------------------------------------------------------------------------
# README documentation
# ---------------------------------------------------------------------------

class TestNewHarnessReadme:
    def _load_readme(self):
        path = os.path.join(WORKSPACE_ROOT, "README.md")
        with open(path) as fh:
            return fh.read()

    @pytest.mark.parametrize("name", NEW_HARNESS_NAMES)
    def test_harness_in_readme(self, name):
        content = self._load_readme()
        assert name in content, f"Harness '{name}' not found in README.md"


# ---------------------------------------------------------------------------
# Router documentation
# ---------------------------------------------------------------------------

class TestNewHarnessRouter:
    def _load_router(self):
        path = os.path.join(AGENTS_DIR, "router.md")
        with open(path) as fh:
            return fh.read()

    @pytest.mark.parametrize("name", NEW_HARNESS_NAMES)
    def test_harness_in_router(self, name):
        content = self._load_router()
        assert name in content, f"Harness '{name}' not found in agents/router.md"
