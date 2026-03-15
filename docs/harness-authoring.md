# Harness Authoring Guide

A harness is an execution contract — it defines *how* Claude Code should approach a class
of tasks. This guide covers everything you need to create, test, and publish a custom
harness.

---

## What a Harness Is (and Isn't)

A harness is **not** a collection of prompts. It is a structured contract with:

- **Trigger conditions** — when to use this harness
- **Execution workflow** — what steps to follow
- **Tool policy** — which tools are allowed
- **Stopping criteria** — when to declare success
- **Cost budget** — token and time limits
- **Failure modes** — what to do when things go wrong

This structure is what allows the router to reason about harness selection and the
evaluator to score results objectively.

---

## Directory Structure

```
harnesses/your-harness-name/
├── agent.md       # Agent definition (role, model, constraints)
├── skill.md       # Execution workflow (step-by-step instructions)
├── contract.yaml  # Execution contract (all structured fields)
└── metadata.json  # Pool membership and performance stats
```

All four files are required. The harness will not load if any file is missing.

---

## `contract.yaml` Reference

This is the most important file. Every field is described below.

```yaml
# ─────────────────────────────────────────────
# Identity
# ─────────────────────────────────────────────
name: your-harness-name
version: 1.0.0
pool: stable        # stable | experimental
                    # New harnesses start as stable.
                    # The runtime may move them to experimental during evolution.

# ─────────────────────────────────────────────
# Trigger Conditions
# ─────────────────────────────────────────────
# The router agent reads these to decide whether this harness is a candidate.
# ALL specified conditions must match for the harness to be considered.
# Omitting a field means "match any value" for that axis.
trigger:
  task_types:       # Required. Which task types this harness handles.
    - bugfix        # Options: bugfix | feature | refactor | research |
    - feature       #          migration | incident | benchmark | "*" (all)

  uncertainty:      # Optional. Acceptable uncertainty levels.
    - low           # Options: low | medium | high
    - medium        # Omit to match all uncertainty levels.

  blast_radius:     # Optional. Acceptable blast radius values.
    - local         # Options: local | cross-module | repo-wide
    - cross-module  # Omit to match all blast radii.

  verifiability:    # Optional. Acceptable verifiability values.
    - easy          # Options: easy | moderate | hard
    - moderate      # Omit to match all verifiability levels.

  domains:          # Optional. Applicable technology domains.
    - backend       # Options: backend | frontend | ml-research | infra | docs
    - frontend      # Omit to match all domains.

  codebase_conditions:  # Optional. Runtime codebase checks.
    - has_test_framework: true  # Only select this harness if tests exist
    # Other conditions (evaluated by the router agent via reasoning):
    # - has_ci_pipeline: true
    # - codebase_size: [small, medium]   # small=<10k LOC, medium=<100k LOC, large=100k+

# ─────────────────────────────────────────────
# Workflow
# ─────────────────────────────────────────────
# Ordered list of step names. These must correspond to steps defined in skill.md.
# The router uses this to understand the execution shape of the harness.
workflow:
  - write_failing_test
  - implement_minimal_code
  - run_tests
  - refactor
  - verify_coverage

# ─────────────────────────────────────────────
# Tool Policy
# ─────────────────────────────────────────────
tool_policy:
  allowed:          # Tools this harness may use
    - Read
    - Write
    - Edit
    - Bash
    - Grep
    - Glob
    # - Agent      # Include only if this harness spawns sub-agents
    # - WebSearch  # Include only if web research is needed

  denied: []        # Tools explicitly forbidden (empty = deny unlisted tools)
                    # Example: ["WebSearch"] if internet access is inappropriate

  restrictions:     # Natural-language constraints on allowed tools
    - "Bash: no destructive git commands (git reset --hard, git clean) without
       explicit user confirmation"
    - "Write: do not overwrite files outside the current project directory"

# ─────────────────────────────────────────────
# Stopping Criteria
# ─────────────────────────────────────────────
# The harness subagent uses these to decide when to stop.
# The evaluator uses these as quality gate inputs.
stopping_criteria:
  - all_tests_pass: true           # Boolean gate
  - coverage_threshold: 80         # Numeric threshold (percentage)
  - max_iterations: 10             # Hard limit on retry loops
  # Other examples:
  # - root_cause_identified: true  # For debugging harnesses
  # - build_success: true
  # - lint_clean: true

# ─────────────────────────────────────────────
# Verification Steps
# ─────────────────────────────────────────────
# Concrete commands the harness runs to verify its work.
# These feed into evidence collection (PostToolUse hook).
verification_steps:
  - run_test_suite    # Runs the project's test suite (npm test, pytest, etc.)
  - lint_check        # Runs the project's linter
  - type_check        # Runs type checking if applicable (tsc, mypy, etc.)
  # - build_check     # Runs the build
  # - security_scan   # Runs a security scanner

# ─────────────────────────────────────────────
# Cost Budget
# ─────────────────────────────────────────────
cost_budget:
  max_tokens: 500000          # Maximum tokens for this harness execution
  max_time_minutes: 30        # Wall-clock timeout
  max_parallel_agents: 1      # Max sub-agents this harness may spawn (usually 1)

# Guidelines:
#   - Research/exploration harnesses: up to 1,000,000 tokens, 60 min
#   - Standard implementation harnesses: 500,000 tokens, 30 min
#   - Review/analysis harnesses: 100,000 tokens, 15 min
#   - Rapid prototype harnesses: 200,000 tokens, 15 min

# ─────────────────────────────────────────────
# Failure Modes
# ─────────────────────────────────────────────
# What to do when the harness cannot complete successfully.
# The orchestrator reads these and executes the specified action.
failure_modes:
  - condition: "tests_fail_after_3_iterations"
    action: fallback
    fallback_harness: "systematic-debugging"
    # Switch to a different harness. The orchestrator re-routes.

  - condition: "timeout"
    action: report_partial
    # Report whatever progress was made. No fallback.

  - condition: "blast_radius_exceeded"
    action: escalate_to_user
    message: "This change affects more files than expected. Please review before proceeding."
    # Pause and ask the user.

  # Other action options:
  # action: rollback
  # rollback_command: "git checkout ."
  # Use for harnesses that make destructive changes and need a clean revert.
```

---

## `agent.md` Best Practices

The agent.md is injected as the system prompt when the harness subagent is spawned.
Write it as you would write a high-quality system prompt.

```markdown
---
name: your-harness-name-agent
description: "One sentence: what this agent does and when it is used"
model: claude-sonnet-4-6
---

You are a [specific role] specialist. Your goal is to [specific objective] by following
the [harness name] workflow defined in the accompanying skill instructions.

## Your Role

[2-3 sentences describing the agent's focus and approach. Be specific about what this
agent prioritizes that generic Claude Code would not.]

## Working Principles

1. **[Principle 1]**: [Concrete behavior this principle produces]
2. **[Principle 2]**: [Concrete behavior this principle produces]
3. **[Principle 3]**: [Concrete behavior this principle produces]

## What You Will NOT Do

- [Anti-pattern 1 relevant to this harness's domain]
- [Anti-pattern 2 — things Claude tends to do that this harness should avoid]

## Output Requirements

At the end of your work, you must output a structured summary:

```json
{
  "status": "complete | partial | failed",
  "steps_completed": ["step_1", "step_2"],
  "verification_results": {
    "tests_passed": true,
    "coverage": 85,
    "lint_clean": true
  },
  "notes": "Any important observations for the evaluator"
}
```
```

**Model selection:**
- `claude-sonnet-4-6` — Use for most harnesses. Fast and capable for implementation,
  debugging, refactoring.
- `claude-opus-4-6` — Use only for harnesses requiring deep reasoning: research,
  multi-perspective review, evolution proposals. Costs 5× more — justify it.

**Common mistakes to avoid in agent.md:**
- Do not describe the harness's workflow steps (that belongs in skill.md)
- Do not include tool lists (that belongs in contract.yaml)
- Do not set model to `claude-opus-4-6` without justification
- Keep the file under 1,500 tokens — it is injected into every execution

---

## `skill.md` Best Practices

The skill.md defines the step-by-step execution workflow. It is injected alongside agent.md.

```markdown
---
name: your-harness-name
description: "What this skill executes"
---

## Overview

[1-2 sentences: what this skill accomplishes and in which scenarios it performs best]

## Pre-conditions

Before starting, verify:
- [ ] [Condition 1 — e.g., "Test framework is present (check for package.json test script)"]
- [ ] [Condition 2]

## Workflow

### Step 1: [Step Name] — [Brief purpose]

[Concrete instructions. What tools to use. What commands to run. What to check.]

**Success criterion:** [How to know this step is done]
**If this step fails:** [What to do — retry, skip, escalate]

### Step 2: [Step Name] — [Brief purpose]

[Instructions]

**Success criterion:** [...]
**If this step fails:** [...]

[Continue for each step in contract.yaml's workflow list]

## Stopping Criteria

Stop and declare success when ALL of the following are true:
- [ ] [Criterion 1 — must match contract.yaml stopping_criteria]
- [ ] [Criterion 2]

## Verification Checklist

Before outputting your completion summary, verify:
- [ ] [Verification step 1 — must match contract.yaml verification_steps]
- [ ] [Verification step 2]

## Known Failure Patterns

| Pattern | Symptom | Response |
|---------|---------|----------|
| [Pattern 1] | [What you observe] | [What to do] |
| [Pattern 2] | [What you observe] | [What to do] |
```

**Best practices:**
- Each step must have exactly one clear success criterion
- Steps must match the `workflow` list in contract.yaml (same names, same order)
- Include concrete tool invocations where possible ("Run `npm test`", not "run tests")
- The stopping criteria section must be consistent with `stopping_criteria` in contract.yaml
- Keep the file under 2,000 tokens

---

## `metadata.json` Reference

```json
{
  "pool": "stable",
  "weight": 1.0,
  "successes": 0,
  "failures": 0,
  "total_runs": 0,
  "consecutive_successes": 0,
  "avg_score": 0
}
```

All values are set to defaults for new harnesses. Do not manually edit this file after
initial creation — the runtime updates it automatically.

**Field meanings:**
- `pool`: `"stable"` or `"experimental"`. New harnesses start as `"stable"`.
- `weight`: Routing weight (1.0 = default priority). Higher = more likely to be selected
  when multiple harnesses match the same task.
- `successes` / `failures`: Cumulative counts across all sessions.
- `consecutive_successes`: Reset to 0 on any failure. Used for experimental→stable promotion.
- `avg_score`: Rolling average of evaluation scores. Used for demotion threshold checks.

---

## Testing Your Harness

### Step 1: Create a fixture

```
fixtures/your-test-scenario/
├── task.md        # A realistic task this harness should handle
└── expected.json  # Expected taxonomy and score range
```

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the expected.json format.

### Step 2: Run the router against your fixture

```
/adaptive-harness:run --harness=your-harness-name "$(cat fixtures/your-test-scenario/task.md)"
```

### Step 3: Verify the outputs

Check:
1. The harness subagent completes without errors
2. The evaluation score falls within the expected range in `expected.json`
3. No unexpected tool usage (check against `tool_policy` in contract.yaml)
4. The completion summary JSON is valid and complete

### Step 4: Run the router without specifying the harness

```
/adaptive-harness:run "$(cat fixtures/your-test-scenario/task.md)"
```

Verify the router selects your harness (or one of the expected harnesses if you listed
multiple in `expected.json`). Repeat 5 times and check that the router selects the
expected harness at least 4 out of 5 times (80% accuracy threshold).

---

## Harness Naming Conventions

| Pattern | Example | When to use |
|---------|---------|-------------|
| `{approach}-{scope}` | `tdd-driven`, `careful-refactor` | General-purpose harnesses |
| `{domain}-{approach}` | `ml-experiment`, `api-driven` | Domain-specific harnesses |
| `{verb}-{noun}` | `research-iteration`, `migration-safe` | Process-oriented harnesses |

Use lowercase kebab-case. Keep names under 30 characters. The name must be unique across
all harnesses in the pool.

---

## Common Harness Patterns

### TDD Pattern (for testable features and bugs)
Steps: write_failing_test → implement → verify_tests → refactor → coverage_check

### Debugging Pattern (for incident response)
Steps: reproduce_bug → isolate_root_cause → implement_fix → verify_fix → add_regression_test

### Research Pattern (for exploratory tasks)
Steps: hypothesize → prototype → measure → analyze → iterate → synthesize

### Refactor Pattern (Mikado method)
Steps: characterize_behavior → identify_dependencies → extract_interface → migrate_one_by_one → verify_preservation

### Migration Pattern
Steps: audit_current_state → plan_migration → backup → migrate_incrementally → verify → document_rollback
