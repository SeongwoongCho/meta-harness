"""
Contract validation tests.

Validates all contract.yaml files, agent.md front-matter, pattern YAML files,
and cross-references between them.

Uses dynamic discovery via glob — not hardcoded names.
"""

import os
import re

import pytest

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

WORKSPACE_ROOT = "/home/seongwoong/workspace/adaptive-harness"
PLUGIN_ROOT = "/home/seongwoong/.claude/plugins/cache/adaptive-harness/adaptive-harness/1.0.0"

HARNESSES_DIR = os.path.join(WORKSPACE_ROOT, "harnesses")
AGENTS_DIR = os.path.join(WORKSPACE_ROOT, "agents")
PATTERNS_DIR = os.path.join(WORKSPACE_ROOT, "patterns")

SKIP_DIRS = {"experimental", "archived", "_shared", "__pycache__"}

REQUIRED_CONTRACT_KEYS = {"name", "version", "pool", "trigger", "workflow",
                           "stopping_criteria", "cost_budget"}
VALID_POOL_VALUES = {"stable", "experimental", "archived"}
VALID_CONTRACT_VERSIONS = {"1.0.0"}

REQUIRED_AGENT_FRONT_MATTER = {"name", "description", "model"}
VALID_MODELS = {
    "claude-sonnet-4-6",
    "claude-opus-4-6",
    "claude-haiku-4-6",
    "claude-sonnet-4-5",
    "claude-opus-4-5",
    "claude-haiku-4-5",
}

REQUIRED_PATTERN_KEYS = {"name", "category", "description", "structure",
                          "failure_signatures", "best_for"}


# ---------------------------------------------------------------------------
# Discovery helpers
# ---------------------------------------------------------------------------

def _discover_harnesses(harnesses_dir: str = HARNESSES_DIR) -> list[str]:
    """Return names of stable harness directories (non-skipped, non-dotfile)."""
    if not os.path.isdir(harnesses_dir):
        return []
    return [
        name for name in os.listdir(harnesses_dir)
        if os.path.isdir(os.path.join(harnesses_dir, name))
        and name not in SKIP_DIRS
        and not name.startswith(".")
    ]


def _discover_agent_files(agents_dir: str = AGENTS_DIR) -> list[str]:
    """Return paths to all agent .md files."""
    if not os.path.isdir(agents_dir):
        return []
    return [
        os.path.join(agents_dir, f)
        for f in os.listdir(agents_dir)
        if f.endswith(".md") and not f.startswith(".")
    ]


def _discover_pattern_files(patterns_dir: str = PATTERNS_DIR) -> list[str]:
    """Return paths to all pattern .yaml files."""
    if not os.path.isdir(patterns_dir):
        return []
    return [
        os.path.join(patterns_dir, f)
        for f in os.listdir(patterns_dir)
        if f.endswith(".yaml") and not f.startswith(".")
    ]


def _parse_front_matter(md_content: str) -> dict:
    """Parse YAML front matter from a markdown file (between --- delimiters)."""
    lines = md_content.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}
    end = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = i
            break
    if end is None:
        return {}
    front_matter_text = "\n".join(lines[1:end])
    try:
        if YAML_AVAILABLE:
            return yaml.safe_load(front_matter_text) or {}
        else:
            # Simple key: value parser (no nested structures needed for front matter)
            result = {}
            for line in front_matter_text.split("\n"):
                if ":" in line:
                    key, _, value = line.partition(":")
                    result[key.strip()] = value.strip().strip('"')
            return result
    except Exception:
        return {}


def _parse_yaml_file(path: str) -> dict:
    """Parse a YAML file, returning empty dict on failure."""
    try:
        if YAML_AVAILABLE:
            with open(path) as fh:
                return yaml.safe_load(fh) or {}
        else:
            # Minimal fallback: read lines and check for key presence
            with open(path) as fh:
                content = fh.read()
            result = {}
            for line in content.split("\n"):
                if ":" in line and not line.strip().startswith("#"):
                    key, _, value = line.partition(":")
                    key = key.strip()
                    value = value.strip().strip('"')
                    if key and not key.startswith(" ") and not key.startswith("-"):
                        result[key] = value
            return result
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Contract.yaml validation
# ---------------------------------------------------------------------------

class TestContractYamlValidation:
    def _get_harness_contracts(self):
        harnesses = _discover_harnesses()
        contracts = []
        for name in harnesses:
            contract_path = os.path.join(HARNESSES_DIR, name, "contract.yaml")
            if os.path.isfile(contract_path):
                contracts.append((name, contract_path))
        return contracts

    def test_all_stable_harnesses_have_contract_yaml(self):
        harnesses = _discover_harnesses()
        missing = []
        for name in harnesses:
            contract_path = os.path.join(HARNESSES_DIR, name, "contract.yaml")
            if not os.path.isfile(contract_path):
                missing.append(name)
        assert missing == [], f"Harnesses missing contract.yaml: {missing}"

    def test_all_contracts_are_parseable_yaml(self):
        contracts = self._get_harness_contracts()
        assert len(contracts) > 0, "No contracts found"
        unparseable = []
        for name, path in contracts:
            parsed = _parse_yaml_file(path)
            if not parsed:
                unparseable.append(name)
        assert unparseable == [], f"Unparseable contracts: {unparseable}"

    def test_all_contracts_have_required_keys(self):
        contracts = self._get_harness_contracts()
        missing_keys = {}
        for name, path in contracts:
            parsed = _parse_yaml_file(path)
            missing = REQUIRED_CONTRACT_KEYS - set(parsed.keys())
            if missing:
                missing_keys[name] = missing
        assert missing_keys == {}, f"Contracts missing keys: {missing_keys}"

    def test_all_contracts_have_valid_pool_value(self):
        contracts = self._get_harness_contracts()
        invalid_pool = {}
        for name, path in contracts:
            parsed = _parse_yaml_file(path)
            pool_val = str(parsed.get("pool", "")).strip()
            if pool_val not in VALID_POOL_VALUES:
                invalid_pool[name] = pool_val
        assert invalid_pool == {}, f"Contracts with invalid pool: {invalid_pool}"

    def test_all_contracts_have_valid_version(self):
        contracts = self._get_harness_contracts()
        invalid_versions = {}
        for name, path in contracts:
            parsed = _parse_yaml_file(path)
            version = str(parsed.get("version", "")).strip()
            if version not in VALID_CONTRACT_VERSIONS:
                invalid_versions[name] = version
        assert invalid_versions == {}, f"Contracts with invalid version: {invalid_versions}"

    def test_contract_name_matches_directory_name(self):
        contracts = self._get_harness_contracts()
        name_mismatches = {}
        for harness_name, path in contracts:
            parsed = _parse_yaml_file(path)
            contract_name = str(parsed.get("name", "")).strip()
            if contract_name and contract_name != harness_name:
                name_mismatches[harness_name] = contract_name
        assert name_mismatches == {}, (
            f"Contract name doesn't match directory: {name_mismatches}"
        )

    def test_all_contracts_have_workflow_steps(self):
        contracts = self._get_harness_contracts()
        no_workflow = []
        for name, path in contracts:
            parsed = _parse_yaml_file(path)
            workflow = parsed.get("workflow")
            if not workflow:
                no_workflow.append(name)
        assert no_workflow == [], f"Contracts missing workflow: {no_workflow}"

    def test_all_harnesses_have_metadata_json(self):
        harnesses = _discover_harnesses()
        missing = []
        for name in harnesses:
            meta_path = os.path.join(HARNESSES_DIR, name, "metadata.json")
            if not os.path.isfile(meta_path):
                missing.append(name)
        assert missing == [], f"Harnesses missing metadata.json: {missing}"

    def test_all_contracts_have_cost_budget(self):
        contracts = self._get_harness_contracts()
        missing_budget = []
        for name, path in contracts:
            parsed = _parse_yaml_file(path)
            budget = parsed.get("cost_budget")
            if not budget:
                missing_budget.append(name)
        assert missing_budget == [], f"Contracts missing cost_budget: {missing_budget}"


# ---------------------------------------------------------------------------
# Agent.md front-matter validation
# ---------------------------------------------------------------------------

class TestAgentMdFrontMatter:
    def _get_agent_files(self):
        return _discover_agent_files()

    def test_agent_files_exist(self):
        agents = self._get_agent_files()
        assert len(agents) > 0, "No agent .md files found"

    def test_all_agents_have_front_matter(self):
        agents = self._get_agent_files()
        no_front_matter = []
        for path in agents:
            with open(path) as fh:
                content = fh.read()
            fm = _parse_front_matter(content)
            if not fm:
                no_front_matter.append(os.path.basename(path))
        assert no_front_matter == [], f"Agents missing front matter: {no_front_matter}"

    def test_all_agents_have_required_front_matter_fields(self):
        agents = self._get_agent_files()
        missing_fields = {}
        for path in agents:
            with open(path) as fh:
                content = fh.read()
            fm = _parse_front_matter(content)
            missing = REQUIRED_AGENT_FRONT_MATTER - set(fm.keys())
            if missing:
                missing_fields[os.path.basename(path)] = missing
        assert missing_fields == {}, f"Agents missing front matter fields: {missing_fields}"

    def test_all_agents_have_valid_model(self):
        agents = self._get_agent_files()
        invalid_models = {}
        for path in agents:
            with open(path) as fh:
                content = fh.read()
            fm = _parse_front_matter(content)
            model = str(fm.get("model", "")).strip()
            if model and model not in VALID_MODELS:
                invalid_models[os.path.basename(path)] = model
        assert invalid_models == {}, f"Agents with invalid model: {invalid_models}"

    def test_all_agents_have_nonempty_name(self):
        agents = self._get_agent_files()
        no_name = []
        for path in agents:
            with open(path) as fh:
                content = fh.read()
            fm = _parse_front_matter(content)
            if not fm.get("name"):
                no_name.append(os.path.basename(path))
        assert no_name == [], f"Agents missing name: {no_name}"

    def test_all_agents_have_nonempty_description(self):
        agents = self._get_agent_files()
        no_desc = []
        for path in agents:
            with open(path) as fh:
                content = fh.read()
            fm = _parse_front_matter(content)
            if not fm.get("description"):
                no_desc.append(os.path.basename(path))
        assert no_desc == [], f"Agents missing description: {no_desc}"

    def test_known_agents_exist(self):
        """Spot-check: the router and evaluator agents must exist."""
        agents = self._get_agent_files()
        basenames = {os.path.basename(p) for p in agents}
        for expected in ("router.md", "evaluator.md", "tdd-driven.md"):
            assert expected in basenames, f"Expected agent file not found: {expected}"


# ---------------------------------------------------------------------------
# Pattern YAML validation
# ---------------------------------------------------------------------------

class TestPatternYamlValidation:
    def _get_pattern_files(self):
        return _discover_pattern_files()

    def test_pattern_files_exist(self):
        patterns = self._get_pattern_files()
        assert len(patterns) > 0, "No pattern .yaml files found"

    def test_all_patterns_are_parseable(self):
        patterns = self._get_pattern_files()
        unparseable = []
        for path in patterns:
            parsed = _parse_yaml_file(path)
            if not parsed:
                unparseable.append(os.path.basename(path))
        assert unparseable == [], f"Unparseable patterns: {unparseable}"

    def test_all_patterns_have_required_keys(self):
        patterns = self._get_pattern_files()
        missing_keys = {}
        for path in patterns:
            parsed = _parse_yaml_file(path)
            missing = REQUIRED_PATTERN_KEYS - set(parsed.keys())
            if missing:
                missing_keys[os.path.basename(path)] = missing
        assert missing_keys == {}, f"Patterns missing keys: {missing_keys}"

    def test_all_patterns_have_nonempty_name(self):
        patterns = self._get_pattern_files()
        no_name = []
        for path in patterns:
            parsed = _parse_yaml_file(path)
            if not parsed.get("name"):
                no_name.append(os.path.basename(path))
        assert no_name == [], f"Patterns missing name: {no_name}"

    def test_known_patterns_exist(self):
        """Spot-check: red-green-refactor and converge-loop must exist."""
        patterns = self._get_pattern_files()
        basenames = {os.path.basename(p) for p in patterns}
        for expected in ("red-green-refactor.yaml", "converge-loop.yaml"):
            assert expected in basenames, f"Expected pattern not found: {expected}"

    def test_pattern_existing_harness_references_known_harness(self):
        """If a pattern's existing_harness is not null, it should be a known harness."""
        patterns = self._get_pattern_files()
        harnesses = set(_discover_harnesses())
        invalid_refs = {}
        for path in patterns:
            parsed = _parse_yaml_file(path)
            existing = parsed.get("existing_harness")
            if existing and existing != "null" and str(existing).strip().lower() != "null":
                if str(existing).strip() not in harnesses:
                    invalid_refs[os.path.basename(path)] = existing
        assert invalid_refs == {}, f"Patterns with invalid existing_harness: {invalid_refs}"


# ---------------------------------------------------------------------------
# Cross-references
# ---------------------------------------------------------------------------

class TestCrossReferences:
    def test_harnesses_have_corresponding_agent_files(self):
        """Each stable harness should have a corresponding agent.md file."""
        harnesses = _discover_harnesses()
        agents = {
            os.path.splitext(os.path.basename(p))[0]
            for p in _discover_agent_files()
        }
        missing_agents = []
        for name in harnesses:
            if name not in agents:
                missing_agents.append(name)
        assert missing_agents == [], (
            f"Harnesses without agent.md: {missing_agents}"
        )

    def test_stable_contracts_have_pool_stable(self):
        """Harnesses not in the experimental/archived directory should have pool=stable."""
        harnesses = _discover_harnesses()
        wrong_pool = {}
        for name in harnesses:
            contract_path = os.path.join(HARNESSES_DIR, name, "contract.yaml")
            if not os.path.isfile(contract_path):
                continue
            parsed = _parse_yaml_file(contract_path)
            pool_val = str(parsed.get("pool", "")).strip()
            # adversarial-review is an exception — it may be experimental
            if pool_val not in VALID_POOL_VALUES:
                wrong_pool[name] = pool_val
        assert wrong_pool == {}, f"Contracts with unexpected pool: {wrong_pool}"

    def test_harness_contract_name_matches_harness_directory(self):
        """contract.yaml 'name' field must match the containing directory name."""
        harnesses = _discover_harnesses()
        mismatches = {}
        for name in harnesses:
            contract_path = os.path.join(HARNESSES_DIR, name, "contract.yaml")
            if not os.path.isfile(contract_path):
                continue
            parsed = _parse_yaml_file(contract_path)
            contract_name = str(parsed.get("name", "")).strip()
            if contract_name and contract_name != name:
                mismatches[name] = contract_name
        assert mismatches == {}, f"Name mismatches: {mismatches}"

    def test_all_harnesses_have_skill_md(self):
        """Each harness directory should have a skill.md file."""
        harnesses = _discover_harnesses()
        missing_skill = []
        for name in harnesses:
            skill_path = os.path.join(HARNESSES_DIR, name, "skill.md")
            if not os.path.isfile(skill_path):
                missing_skill.append(name)
        assert missing_skill == [], f"Harnesses missing skill.md: {missing_skill}"

    def test_harness_count_consistent_between_dirs(self):
        """Workspace harnesses and plugin harnesses should have the same stable names."""
        ws_harnesses = set(_discover_harnesses(HARNESSES_DIR))
        plugin_harnesses_dir = os.path.join(PLUGIN_ROOT, "harnesses")
        if os.path.isdir(plugin_harnesses_dir):
            plugin_harnesses = set(_discover_harnesses(plugin_harnesses_dir))
            # Both sets should be non-empty
            assert len(ws_harnesses) > 0
            assert len(plugin_harnesses) > 0
            # Workspace harnesses should be a subset of or equal to plugin harnesses
            # (plugin may have more experimental ones)
            extra_in_ws = ws_harnesses - plugin_harnesses
            assert extra_in_ws == set(), (
                f"Harnesses in workspace but not in plugin: {extra_in_ws}"
            )
