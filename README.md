# meta-harness

**A self-improving harness router and evaluator for Claude Code.**

meta-harness watches every task you give Claude Code, routes it to the optimal execution
workflow (harness), scores the result against domain-specific criteria, and — over time —
evolves those workflows to fit your codebase better.

> Unlike static skill packs, meta-harness gets smarter the more you use it.

---

## Demo Scenes

### Scene 1 — Same task, different harnesses, score comparison

```
User: Fix the login bug where empty email crashes the server

[meta-harness router]
  Task taxonomy: bugfix | low uncertainty | local | easy | backend
  Candidates scored:
    tdd-driven          → trigger match: YES  | historical weight: 1.00 | score: 0.92
    systematic-debugging → trigger match: YES  | historical weight: 0.88 | score: 0.81
    rapid-prototype      → trigger match: NO   | (skipped)
  Selected: tdd-driven (score 0.92)
  Bound protocol: code-quality-standard

[tdd-driven subagent]
  Step 1: Write failing test for empty-email path   ✓
  Step 2: Implement null guard in validateEmail()   ✓
  Step 3: Run test suite (47/47 pass)               ✓
  Step 4: Lint check                                ✓

[evaluator]
  build_success:    1.00
  test_pass_rate:   1.00
  code_quality:     0.91
  robustness:       0.88
  overall:          0.94  ← harness weight updated: 1.00 → 1.02
```

### Scene 2 — Hard task triggers conditional ensemble

```
User: Research and implement a new caching strategy to reduce p99 latency below 50ms.
      Requirements are still exploratory.

[meta-harness router]
  Task taxonomy: research | HIGH uncertainty | repo-wide | HARD verifiability | backend
  Ensemble condition: uncertainty=high AND verifiability=hard  → TRIGGERED

[ensemble engine — 2 parallel subagents]
  Subagent A: research-iteration harness
    → Hypothesis: Redis sorted-set with TTL sharding
    → Benchmark result: p99 = 42ms  ✓
  Subagent B: rapid-prototype harness
    → Approach: in-process LRU + async write-through
    → Benchmark result: p99 = 38ms  ✓

[synthesizer]
  Comparing A (reliability: high, complexity: medium) vs B (reliability: medium, complexity: low)
  Merged recommendation: B's LRU core + A's TTL sharding for hot-key protection
  Final p99: 36ms
```

### Scene 3 — Repeated tasks improve router choice over time

```
Session 1 — "Add input validation to the registration form"
  Router selects: tdd-driven  (default weight 1.0)
  Evaluation score: 0.71  (tests pass but coverage only 72%)
  Weight update: tdd-driven → 0.97 for this task shape

Session 4 — "Add validation to the password-reset form"
  Same taxonomy shape detected in history
  Router sees: tdd-driven weight=0.97 vs systematic-debugging weight=1.0
  Selects: systematic-debugging (higher weight for this shape)
  Evaluation score: 0.89  ← improvement

Session 8 — "Add validation to the profile-update form"
  Router history: systematic-debugging 3× score avg=0.87
  Selects: systematic-debugging with confidence (weight=1.08)
  Evaluation score: 0.91  ← router has learned your codebase's validation pattern
```

---

## What It Does

meta-harness is a **meta-orchestration layer** that sits above your Claude Code workflows:

```
User Task
    │
    ▼
┌──────────────────────────────────────────┐
│  meta-harness (Orchestrator)             │
│                                          │
│  ┌──────────────┐  ┌──────────────────┐  │
│  │ Task         │  │  Decision        │  │
│  │ Classifier   │──▶  Engine          │  │
│  │ (6-axis      │  │  (router +       │  │
│  │  taxonomy)   │  │   explainability)│  │
│  └──────────────┘  └────────┬─────────┘  │
│                             │            │
│  ┌──────────────────────────▼─────────┐  │
│  │         Harness Pool               │  │
│  │  ┌──────────┐  ┌──────────────┐    │  │
│  │  │ Stable   │  │ Experimental │    │  │
│  │  │ Pool     │  │ Pool         │    │  │
│  │  └──────────┘  └──────────────┘    │  │
│  └────────────────────────────────────┘  │
│       │                                  │
│  ┌────▼──────┐  ┌────────────────────┐   │
│  │ Ensemble  │  │ Evaluation Engine  │   │
│  │ Engine    │  │ (protocol-based)   │   │
│  │ (cond.    │  └─────────┬──────────┘   │
│  │  fan-out) │           │              │
│  └───────────┘  ┌────────▼───────────┐   │
│                 │ Update Engine       │   │
│                 │ (hybrid timing)     │   │
│                 └────────────────────┘   │
└──────────┬───────────────────────────────┘
           │
           ▼
    Subagent(s) execute task
    with selected harness(es)
    + bound evaluation protocol
```

**Five stages, all included in v1.0:**

| Stage | What happens |
|-------|-------------|
| **1. Initialization** | Load built-in harnesses; optionally run `meta-harness-init` to define domain criteria |
| **2. Decision** | Classify task on 6 axes; select optimal harness from pool by taxonomy + weight |
| **3. Ensemble** | If `uncertainty=high AND (verifiability=hard OR blast_radius=repo-wide)`, run 2+ harnesses in parallel and synthesize |
| **4. Evaluation** | Score result against bound evaluation protocol (universal + custom dimensions) |
| **5. Update** | Update weights in real-time; evolve harness content next-session via experimental pool |

---

## Installation

```bash
claude plugin install meta-harness
```

Or clone and install locally:

```bash
git clone https://github.com/<owner>/meta-harness
claude plugin install ./meta-harness
```

---

## Quick Start

### 1. Install the plugin

```bash
claude plugin install meta-harness
```

### 2. Initialize for your project (optional but recommended)

```
/meta-harness-init
```

This runs an interactive Q&A to define:
- Your project's domain (backend / frontend / ml-research / infra / docs)
- Custom evaluation dimensions (e.g., "model accuracy" for ML projects)
- Ensemble trigger preferences
- Evolution aggressiveness

A `.meta-harness/config.yaml` file is created. Sensible defaults apply if you skip init.

### 3. Enable auto-mode

```
/using-meta-harness-default
```

From this point forward, every task you give Claude Code in this session is automatically
routed through the meta-harness pipeline. No further commands needed.

### 4. Use Claude Code normally

```
Fix the authentication bug where empty passwords are accepted
```

meta-harness intercepts the task, routes it, executes via the optimal harness, evaluates
the result, and updates its knowledge — transparently.

### 5. Check pool status anytime

```
/meta-harness-status
```

---

## Architecture Overview

### Core Principle: Harness ≠ Evaluation Protocol

These are two independent first-class objects:

| Object | Answers | Example |
|--------|---------|---------|
| **Harness** | *How to work* — execution contract | `tdd-driven`, `careful-refactor` |
| **Evaluation Protocol** | *What success means* — scoring criteria | `code-quality-standard`, `ml-research` |

The same harness can be evaluated by different protocols depending on context. A
`research-iteration` harness used in a DL project binds to the `ml-research` protocol;
the same harness used in a web project binds to `web-app-performance`.

### Task Taxonomy (6 Axes)

Every incoming task is classified on 6 axes by the `router` agent (LLM reasoning, not
keyword matching):

| Axis | Values |
|------|--------|
| `task_type` | `bugfix` / `feature` / `refactor` / `research` / `migration` / `incident` / `benchmark` |
| `uncertainty` | `low` / `medium` / `high` |
| `blast_radius` | `local` / `cross-module` / `repo-wide` |
| `verifiability` | `easy` / `moderate` / `hard` |
| `latency_sensitivity` | `low` / `high` |
| `domain` | `backend` / `frontend` / `ml-research` / `infra` / `docs` |

### Hook Lifecycle

```
Session Start
    │  session-start.sh
    │  Inject using-meta-harness-default/SKILL.md as additionalContext
    ▼
User Message (every turn)
    │  prompt-interceptor.sh
    │  Reinforce meta-harness routing protocol (<500 bytes)
    ▼
Task Execution (PostToolUse: Bash)
    │  collect-evidence.sh
    │  Capture build/test/lint output → .meta-harness/sessions/{id}/evidence/
    ▼
Subagent Completes
    │  subagent-complete.sh
    │  Notify orchestrator: harness subagent finished → trigger evaluation
    ▼
Session End
       session-end.sh
       Merge per-session weight updates → .meta-harness/harness-pool.json (atomic write)
       Clean up session directories older than 30 days
```

### Orchestration Flow (Single Harness)

```
Router agent
  → taxonomy JSON + selected_harness + bound_protocol
Orchestrator (SKILL.md in main context)
  → Spawn harness subagent (agent.md + skill.md injected)
  → subagent executes task
  → Evidence collected via PostToolUse hook
Evaluator agent
  → Score results against protocol dimensions
  → Return dimension scores + overall score + improvement suggestions
Orchestrator
  → Update in-memory weights
  → Write eval-{timestamp}.json to .meta-harness/sessions/{id}/
```

### Ensemble Flow (Conditional)

Triggered when `uncertainty=high AND (verifiability=hard OR blast_radius=repo-wide)`:

```
Orchestrator
  → Spawn harness-A subagent (parallel)
  → Spawn harness-B subagent (parallel)
  → Wait for both
  → Spawn synthesizer agent with both results
  → Synthesizer merges into final result
```

### State Layout

```
.meta-harness/
├── harness-pool.json           # Shared pool state (weights, pool membership)
├── harness-pool.json.bak       # Backup before last write
├── sessions/
│   └── {session-id}/
│       ├── weights.json        # Session-local weight updates
│       ├── evidence/           # Collected evidence (build, test, lint output)
│       └── eval-{timestamp}.json  # Evaluation results
├── evaluation-logs/
│   └── {harness-name}/
│       └── {date}-{hash}.json  # Historical evaluations per harness
└── evolution-proposals/
    └── {proposal-id}.json      # Pending harness content modifications
```

All state files are stored in `.meta-harness/` in your project root and should be gitignored. The `meta-harness-init` command adds `.meta-harness/` to your `.gitignore` automatically.

---

## Configuration Reference

After running `/meta-harness-init`, a `.meta-harness/config.yaml` file is created:

```yaml
version: "1.0.0"
domain: backend                  # backend | frontend | ml-research | infra | docs

evaluation:
  protocol: code-quality-standard  # default bound protocol
  custom_dimensions:
    - name: api_response_time
      weight: 0.15
      type: score_0_to_1
      description: "P99 response time within SLA"

ensemble:
  enabled: true
  trigger_override: null          # null = use default trigger conditions
  # Custom override example:
  # trigger_override:
  #   uncertainty: [high]
  #   verifiability: [hard]

evolution:
  enabled: true
  promotion_threshold: 5          # consecutive successes required for stable promotion
  demotion_threshold: 0.6         # overall score below this triggers demotion review
  aggressiveness: conservative    # conservative | moderate | aggressive
```

---

## Harness Chaining

For complex tasks, the router can select a **harness chain** — a sequence of harnesses executed one after another. Each harness in the chain receives the original task description plus the accumulated results of all prior harnesses as context.

```
harness_chain: ["ralplan-consensus", "careful-refactor", "code-review"]
                      │                      │                  │
                      ▼                      ▼                  ▼
                 Create plan          Execute plan          Review result
                 (opus model)        (with plan as         (with full
                                      context)              chain context)
```

The router decides freely whether to chain based on task complexity:

| Task Complexity | Typical Chain |
|----------------|---------------|
| Low uncertainty, local change | `["tdd-driven"]` — single harness |
| Medium uncertainty, cross-module | `["ralplan-consensus", "tdd-driven"]` — plan then execute |
| High uncertainty, repo-wide | `["ralplan-consensus", "careful-refactor", "code-review"]` — full cycle |
| Needs iterative convergence | `["ralplan-consensus", "ralph-loop"]` — plan then persist |

Evaluation runs **once** at the end of the full chain, not after each step.

## Built-in Harnesses

| Harness | Best For | Trigger Conditions | Model |
|---------|----------|--------------------|-------|
| **tdd-driven** | Bugs and features with clear test expectations | `task_type: [bugfix, feature]`, `uncertainty: [low, medium]`, `verifiability: [easy, moderate]` | Sonnet |
| **systematic-debugging** | Root cause analysis of complex bugs | `task_type: [bugfix, incident]` | Sonnet |
| **rapid-prototype** | Fast MVP when latency matters | `task_type: [feature]`, `uncertainty: [low]`, `latency_sensitivity: high` | Sonnet |
| **research-iteration** | Exploratory research with unclear requirements | `task_type: [research, benchmark]`, `uncertainty: [high]` | Opus |
| **careful-refactor** | Safe structural refactoring (Mikado method) | `task_type: [refactor]`, `blast_radius: [cross-module, repo-wide]` | Sonnet |
| **code-review** | Multi-perspective code review | `task_type: [*]`, `post_execution: true` | Opus |
| **migration-safe** | Dependency upgrades and migrations | `task_type: [migration]`, `blast_radius: [repo-wide]` | Sonnet |
| **ralplan-consensus** | Upfront planning with self-review (first step in chains) | `uncertainty: [medium, high]`, `blast_radius: [cross-module, repo-wide]` | Opus |
| **ralph-loop** | Persistent execution until acceptance criteria pass | `uncertainty: [medium, high]`, max 10 iterations | Sonnet |

---

## Built-in Evaluation Protocols

| Protocol | Universal Dims | Custom Dims | Best For |
|----------|---------------|-------------|----------|
| **code-quality-standard** | build, tests, quality, robustness, maintainability, security, readability, error_handling | None | General purpose |
| **ml-research** | build, tests, quality, robustness | model_accuracy, training_efficiency, reproducibility, experiment_tracking | ML / AI projects |
| **web-app-performance** | build, tests, quality, security | response_time, ui_consistency, accessibility, lighthouse_score | Web applications |
| **cli-tool-ux** | build, tests, quality, error_handling | ux_quality, error_messages, help_text, documentation_coverage | CLI tools |

---

## Community Contributions

meta-harness grows through three contribution layers:

### Layer 1: Harnesses
Contribute a new execution workflow. Contributors write markdown — no code required.

```
harnesses/your-harness-name/
├── agent.md       # Agent role, model, constraints (also serves as agent registration)
├── skill.md       # Step-by-step workflow
├── contract.yaml  # Trigger conditions, tool policy, stopping criteria, cost budget
└── metadata.json  # Pool membership and initial stats
```

Each harness's `agent.md` is symlinked into `agents/` for subagent type registration:
```
agents/your-harness-name.md → ../harnesses/your-harness-name/agent.md
```
This means the harness directory is the **single source of truth** — evolution changes to `agent.md` automatically update the agent registration. When contributing a new harness, create the symlink as well.

See [docs/harness-authoring.md](docs/harness-authoring.md) for the full guide.

### Layer 2: Evaluation Protocols
Contribute domain-specific scoring criteria.

```
protocols/your-protocol-name/
└── protocol.yaml  # Dimensions, weights, quality gate configuration
```

See [docs/protocol-authoring.md](docs/protocol-authoring.md) for the full guide.

### Layer 3: Task Fixtures
Contribute reproducible benchmark scenarios so the community can measure harness
performance consistently.

```
fixtures/your-scenario/
├── task.md        # Task description
└── expected.json  # Expected taxonomy, harness, score range
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for submission guidelines and review process.

---

## Why meta-harness?

| Tool | What it does | Limitation |
|------|-------------|------------|
| superpowers | 14 static skills | Same workflow forever |
| oh-my-claudecode | Orchestration layer | You choose the workflow |
| **meta-harness** | Self-improving routing + evaluation | **Gets better with use** |

meta-harness does not replace superpowers or oh-my-claudecode — it is a meta-layer that
can orchestrate them. Its core value is the feedback loop: every task teaches it which
workflows work best in your specific codebase.

---

## License

MIT — see [LICENSE](LICENSE).
