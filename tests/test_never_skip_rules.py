"""
Tests that the NEVER-SKIP rules and strengthened prompt-interceptor
are correctly present in the source files.

These are structural/content tests ensuring the enforcement language
exists and hasn't been accidentally removed.
"""

import os
import re

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_FILE = os.path.join(
    WORKSPACE_ROOT, "skills", "using-adaptive-harness", "SKILL.md"
)
INTERCEPTOR_FILE = os.path.join(WORKSPACE_ROOT, "hooks", "prompt-interceptor.sh")


class TestNeverSkipRulesInSkillMd:
    """Ensure SKILL.md contains the NEVER-SKIP enforcement section."""

    def _read_skill(self):
        with open(SKILL_FILE) as f:
            return f.read()

    def test_never_skip_section_exists(self):
        content = self._read_skill()
        assert "## NEVER-SKIP Rules" in content

    def test_meta_task_antipattern_documented(self):
        """The most common bypass: 'this modifies the plugin itself'."""
        content = self._read_skill()
        assert "modifies the adaptive-harness plugin itself" in content

    def test_too_simple_antipattern_documented(self):
        content = self._read_skill()
        assert "too simple for the pipeline" in content.lower() or "too simple" in content.lower()

    def test_circular_antipattern_documented(self):
        content = self._read_skill()
        assert "circular" in content.lower() or "recursive" in content.lower()

    def test_explore_before_route_antipattern_documented(self):
        content = self._read_skill()
        assert "explore the codebase first before routing" in content.lower() or \
               "explore" in content.lower() and "before routing" in content.lower()

    def test_self_check_instruction_exists(self):
        """The concrete self-check: first tool call must be router."""
        content = self._read_skill()
        assert "first tool call" in content.lower()
        assert "adaptive-harness:router" in content

    def test_step1_critical_instruction_exists(self):
        """Step 1 must contain the CRITICAL first-tool-call enforcement."""
        content = self._read_skill()
        # Find Step 1 section
        step1_match = re.search(
            r"### Step 1: Receive Task.*?### Step 2:",
            content,
            re.DOTALL,
        )
        assert step1_match is not None, "Step 1 section not found"
        step1_text = step1_match.group(0)
        assert "CRITICAL" in step1_text
        assert "FIRST tool call" in step1_text or "first tool call" in step1_text.lower()

    def test_never_bypass_router_in_constraints(self):
        """Key Design Constraints must include the no-bypass rule."""
        content = self._read_skill()
        assert "NEVER bypass the router" in content

    def test_at_least_six_antipatterns(self):
        """Ensure we document at least 6 invalid rationalizations."""
        content = self._read_skill()
        # Count numbered items in the NEVER-SKIP section
        section_match = re.search(
            r"## NEVER-SKIP Rules.*?---",
            content,
            re.DOTALL,
        )
        assert section_match is not None
        section = section_match.group(0)
        numbered = re.findall(r"^\d+\.", section, re.MULTILINE)
        assert len(numbered) >= 6, f"Expected >=6 antipatterns, found {len(numbered)}"


class TestPromptInterceptorEnforcement:
    """Ensure prompt-interceptor.sh uses strong enforcement language."""

    def _read_interceptor(self):
        with open(INTERCEPTOR_FILE) as f:
            return f.read()

    def test_mandatory_keyword_present(self):
        content = self._read_interceptor()
        assert "MANDATORY" in content

    def test_first_action_must_be_router(self):
        content = self._read_interceptor()
        assert "adaptive-harness:router" in content

    def test_do_not_read_files_before_routing(self):
        content = self._read_interceptor()
        assert "Do NOT read files" in content or "Do NOT explore" in content

    def test_antipattern_examples_in_message(self):
        """The interceptor should mention common bypass rationalizations."""
        content = self._read_interceptor()
        assert "modifies the plugin" in content or "too simple" in content

    def test_auto_mode_message_is_not_weak(self):
        """The old weak message 'Route this task...' should be replaced."""
        content = self._read_interceptor()
        # The old weak message should NOT exist
        assert "before responding directly" not in content
