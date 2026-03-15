# Contributing to adaptive-harness

Thank you for contributing. adaptive-harness grows through three independent layers — you can
contribute to any one of them without touching the others.

---

## Contribution Layers

| Layer | What you write | Effort |
|-------|---------------|--------|
| **1. Harnesses** | Execution workflows (markdown only) | Medium |
| **2. Task Fixtures** | Benchmark scenarios (markdown + JSON) | Small |

No compiled code is required for any layer. Contributors write markdown and YAML.

---

## Layer 1: Contributing a Harness

A harness is an execution contract — it defines *how* Claude Code should approach a class
of tasks.

### Directory Structure

```
agents/your-harness-name.md    # Agent role definition (Claude Code agent registry)
harnesses/your-harness-name/
├── skill.md       # Step-by-step execution workflow
├── contract.yaml  # Execution contract (trigger, tool_policy, stopping_criteria, etc.)
└── metadata.json  # Pool membership and initial performance stats
```

### Files Required

#### `agent.md`

YAML frontmatter followed by the agent's role description:

```markdown
---
name: your-harness-name-agent
description: "One sentence: what this agent does and when"
model: claude-sonnet-4-6
---

You are a [role] specialist. Your goal is to [objective].

## Constraints
- [constraint 1]
- [constraint 2]

## Output Format
[describe expected outputs]
```

**Model guidelines:**
- Use `claude-sonnet-4-6` for most harnesses (fast, capable)
- Use `claude-opus-4-6` only for research, review, or synthesis tasks (higher cost)
- Do not hard-code model versions that may become outdated — prefer major version aliases
  when the plugin runtime supports them

#### `skill.md`

YAML frontmatter followed by the workflow steps:

```markdown
---
name: your-harness-name
description: "What this skill does"
---

## Workflow

### Step 1: [Phase Name]
[Concrete instructions for this phase]

### Step 2: [Phase Name]
[Concrete instructions for this phase]

## Stopping Criteria
[When to stop and declare success]

## Failure Handling
[What to do if a step fails]
```

**Best practices for skill.md:**
- Number steps explicitly — the orchestrator reads step order
- Each step should have a single, verifiable outcome
- Include explicit stopping criteria (what "done" means)
- Include failure handling for each major step
- Keep steps concrete, not aspirational ("Run `npm test`", not "Ensure tests pass")

#### `contract.yaml`

```yaml
name: your-harness-name
version: 1.0.0
pool: stable        # new contributions start as stable; evolution may move to experimental

trigger:
  task_types: [bugfix, feature]      # which task types this harness handles
  uncertainty: [low, medium]         # acceptable uncertainty levels
  blast_radius: [local, cross-module] # acceptable blast radius values
  verifiability: [easy, moderate]    # acceptable verifiability values
  domains: [backend, frontend]       # applicable domains (omit for all domains)
  codebase_conditions: []            # optional: e.g., has_test_framework: true

workflow:
  - step_1_name
  - step_2_name
  - step_3_name

tool_policy:
  allowed: [Read, Write, Edit, Bash, Grep, Glob]
  denied: []
  restrictions:
    - "Bash: no destructive git commands without explicit user confirmation"

stopping_criteria:
  - all_tests_pass: true
  - max_iterations: 10

verification_steps:
  - run_test_suite
  - lint_check

cost_budget:
  max_tokens: 500000
  max_time_minutes: 30
  max_parallel_agents: 1

failure_modes:
  - condition: "tests_fail_after_3_iterations"
    action: fallback
    fallback_harness: "systematic-debugging"
  - condition: "timeout"
    action: report_partial
```

**Trigger field rules:**
- `task_types`: at least one value required; use `["*"]` to match all types
- `uncertainty`, `blast_radius`, `verifiability`: omit a field to match all values
- Overly broad triggers (all fields omitted) make the harness compete with everything —
  prefer specific triggers so the router can differentiate

#### `metadata.json`

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

All new harnesses start with default stats. The runtime updates these as the harness is used.

### Testing Your Harness with Fixtures

Before submitting, validate your harness against at least one fixture:

1. Create a fixture under `fixtures/your-scenario/` (see Layer 2 below)
2. Run the router manually against your fixture's `task.md`:
   ```
   /adaptive-harness:run --harness=your-harness-name "$(cat fixtures/your-scenario/task.md)"
   ```
3. Verify: the harness completes without errors and the evaluation score falls within the
   range specified in `expected.json`

**Pass criteria for a new harness PR:**
- Router selects the harness for its intended task types in at least 80% of test runs
- Evaluation score is within ±0.15 of the expected range in `expected.json`
- All required files present and schema-conformant (validated by CI)

### Submission

1. Fork the repository
2. Create a branch: `git checkout -b harness/your-harness-name`
3. Add your harness directory under `harnesses/`
4. Add at least one fixture under `fixtures/`
5. Open a pull request with:
   - A description of what problem this harness solves
   - Which task types it targets
   - Example tasks it handles well (and handles poorly)
   - Evidence: evaluation score from at least one fixture run

---

## Layer 2: Contributing Task Fixtures

Fixtures are reproducible benchmark scenarios. They let the community measure whether the
router selects the right harness and whether evaluation scores are consistent.

### Directory Structure

```
fixtures/your-scenario-name/
├── task.md        # Task description
└── expected.json  # Expected router output and score range
```

### `task.md` Format

Write the task as a user would actually phrase it to Claude Code. Include:
- A clear task description
- Relevant context (file locations, reproduction steps, constraints)
- Explicit acceptance criteria or definition of done

The task description should be realistic — copy from real issues or user stories you have
encountered.

### `expected.json` Format

```json
{
  "expected_taxonomy": {
    "task_type": "bugfix",
    "uncertainty": "low",
    "blast_radius": "local",
    "verifiability": "easy",
    "latency_sensitivity": "low",
    "domain": "backend"
  },
  "expected_harness": ["tdd-driven", "systematic-debugging"],
  "expected_score_range": {
    "min": 0.7,
    "max": 1.0
  },
  "reasoning": "Explain why this taxonomy and harness selection are correct. This is read by reviewers.",
  "pass_criteria": {
    "router_accuracy_threshold": 0.8,
    "score_tolerance": 0.15
  }
}
```

**`expected_harness`** is an array — list all harnesses that are acceptable selections for
this task. The router passes if it selects any harness in this list.

**`expected_score_range`** defines the acceptable score range. A fixture is considered
passing if the evaluation score falls within `[min - tolerance, max + tolerance]` where
`tolerance` defaults to `0.15`.

### Fixture Quality Guidelines

- **Be specific:** Vague tasks produce inconsistent taxonomy classifications. Include file
  paths, error messages, and concrete acceptance criteria.
- **Be realistic:** Use task descriptions from real projects, not toy examples.
- **Cover edge cases:** Good fixture sets include at least one ambiguous task (to test
  the router's uncertainty classification), one ensemble-triggering task (high uncertainty
  + hard verifiability), and one fast-path task (trivial follow-up).
- **Justify your expected taxonomy:** The `reasoning` field is required and reviewed.

### Submission

1. Fork and create a branch: `git checkout -b fixture/your-scenario-name`
2. Add your fixture directory under `fixtures/`
3. Open a pull request with:
   - The scenario category (bugfix / feature / refactor / research / migration)
   - Why this scenario is a useful benchmark
   - Your expected taxonomy reasoning

---

## General Guidelines

### Code of Conduct

Be respectful. Focus on technical substance. Assume good faith.

### Review Process

All PRs are reviewed for:
1. **Schema conformance** — harness/fixture files validate against their schemas
2. **Trigger specificity** — harness triggers are specific enough to be useful
3. **Fixture realism** — task descriptions reflect real-world usage
4. **Documentation** — reasoning fields are complete and accurate

### Versioning

- Harness changes that alter behavior increment the minor version (`1.0.0` → `1.1.0`)
- Breaking changes to `contract.yaml` schema increment the major version
- Fixtures do not have versions — they are living benchmarks

### Questions

Open an issue with the `question` label. For design discussions, open a discussion thread.
