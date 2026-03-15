<p align="center">
  <h1 align="center">adaptive-harness</h1>
  <p align="center">
    <strong>A self-improving harness router for Claude Code.</strong><br/>
    It watches every task, picks the best workflow, scores the result, and evolves — automatically.
  </p>
  <p align="center">
    <a href="#installation">Install</a> &nbsp;&bull;&nbsp;
    <a href="#how-it-works">How It Works</a> &nbsp;&bull;&nbsp;
    <a href="#built-in-harnesses">Harnesses</a> &nbsp;&bull;&nbsp;
    <a href="#contributing">Contributing</a>
  </p>
</p>

---

> **Unlike static skill packs, adaptive-harness gets smarter the more you use it.**

```
You: Fix the login bug where empty email crashes the server

[adaptive-harness]
  Classified:  bugfix | low uncertainty | local | backend
  Selected:    tdd-driven (score 0.92)  >  systematic-debugging (0.81)

[tdd-driven subagent]
  1. Write failing test for empty-email path   ✓
  2. Implement null guard in validateEmail()   ✓
  3. Run test suite (47/47 pass)               ✓

[evaluator]
  correctness: 1.00 | completeness: 1.00 | quality: 0.91
  robustness: 0.88 | clarity: 0.95 | verifiability: 0.92
  overall: 0.94  ← harness weight updated: 1.00 → 1.02
```

After 8 sessions on similar tasks, the router **learns your codebase's patterns** and consistently picks the highest-scoring workflow.

---

## How It Works

```
User Task
    │
    ▼
┌─────────────────────────────────────┐
│  1. Classify    6-axis taxonomy     │
│  2. Route       best harness(es)    │
│  3. Execute     subagent pipeline   │
│  4. Evaluate    6-dim scoring       │
│  5. Evolve      update weights      │
└─────────────────────────────────────┘
```

**Three levels of self-improvement:**

| Level | What improves | How |
|-------|--------------|-----|
| **Routing** | Which harness gets picked | Weights adjust after every evaluation |
| **Content** | What the harness actually does | Evolution manager rewrites agent personas and `skill.md` via A/B testing |
| **Genesis** | Which harnesses exist | Evolution manager creates new harnesses by combining existing ones |

Hard tasks (`uncertainty=high` **and** `verifiability=hard` or `blast_radius=repo-wide`) automatically trigger **ensemble mode** — two harnesses run in parallel, a synthesizer merges the best of both.

---

## Installation

```bash
claude plugin marketplace add https://github.com/SeongwoongCho/adaptive-harness
claude plugin install adaptive-harness@adaptive-harness
```

Then start a new Claude Code session.

---

## Quick Start

```bash
cd your-project
claude                              # new session — hooks load automatically
```

```
/adaptive-harness:init --general        # one-command setup with sensible defaults
```

That's it. Every task is now routed through the adaptive-harness pipeline automatically.

```
# Or run explicitly with options
/adaptive-harness:run "Refactor the payment module"
/adaptive-harness:run "Build a new feature"              # interview runs by default
/adaptive-harness:run --skip-interview "Build a new feature"  # skip interview
/adaptive-harness:run --harness=tdd-driven "Fix the login bug"
```

---

## Built-in Harnesses

| Harness | Best For | Model |
|---------|----------|-------|
| **tdd-driven** | Strict red-green-refactor cycles with enforced test coverage gates | Sonnet |
| **systematic-debugging** | Root cause analysis through structured reproduce-isolate-fix-verify phases | Sonnet |
| **rapid-prototype** | Fast MVP building with speed as the primary constraint | Sonnet |
| **research-iteration** | Hypothesis-driven cycles for high-uncertainty problems with rigorous measurement | Opus |
| **careful-refactor** | Safe refactoring via Mikado method without changing observable behavior | Sonnet |
| **code-review** | Multi-perspective review across security, quality, performance, and maintainability | Opus |
| **migration-safe** | Schema, dependency, and API migrations with audit trails and rollback plans | Sonnet |
| **ralplan-consensus** | Implementation planning with self-review — analyzes, plans, then challenges its own assumptions | Opus |
| **ralph-loop** | Persistent execution loop until all acceptance criteria pass (max iterations bounded) | Sonnet |
| **engineering-retro** | Weekly retrospective with commit history analysis, contributor metrics, trend tracking, and growth coaching | Sonnet |
| **plan-review** | Challenges scope and reviews architecture, quality, tests, and performance one issue at a time with failure mode analysis | Opus |
| **qa-testing** | Tests applications like a real user, computes a health score, and produces a structured report with screenshot evidence | Sonnet |
| **pre-landing-review** | Pre-merge diff review with critical (blocking) and informational (advisory) passes and interactive resolution | Sonnet |
| **ship-workflow** | Automated release: merges main, runs tests, bumps version, generates changelog, creates bisectable commits, and opens a PR | Sonnet |

### Experimental Harnesses

| Harness | Best For | Model |
|---------|----------|-------|
| **progressive-refinement** | Iterative quality improvement — rough solution first, then targets weakest dimension each pass | Sonnet |
| **divide-and-conquer** | Splits large tasks into independent sub-tasks, solves in isolation, integrates and verifies | Sonnet |
| **adversarial-review** | Implements a solution, then deliberately tries to break it with adversarial tests and edge-case attacks | Sonnet |
| **spike-then-harden** | Two-phase: fast throwaway prototype to learn the problem space, then production-quality rewrite | Sonnet |

The router supports **harness chaining** — e.g. `plan → execute → review` for complex tasks. Chains are **adaptive**: if a harness discovers mid-execution that the next planned step is wrong, it emits a `next_harness_hint` and the orchestrator reroutes dynamically.

---

## Task Taxonomy (6 Axes)

Every task is classified by LLM reasoning (not keyword matching):

| Axis | Values |
|------|--------|
| `task_type` | bugfix / feature / refactor / research / migration / incident / benchmark |
| `uncertainty` | low / medium / high |
| `blast_radius` | local / cross-module / repo-wide |
| `verifiability` | easy / moderate / hard |
| `latency_sensitivity` | low / high |
| `domain` | backend / frontend / mobile / ml-research / data-engineering / devops / security / infra / docs |
| `domain_hint` | *(optional)* free-text hint for mixed-domain tasks — logged for analytics, not used in routing (e.g., `"also touches devops"`, `"Spark ETL pipeline"`) |

---

## Evaluation Dimensions

Every task result is scored on **6 fixed dimensions** with fixed weights:

| Dimension | Weight | What it measures |
|-----------|--------|-----------------|
| **correctness** | 0.25 | Does the output satisfy stated requirements? |
| **completeness** | 0.20 | Does the output cover the full scope? |
| **quality** | 0.20 | Structural and stylistic quality |
| **robustness** | 0.10 | Edge case and failure mode handling |
| **clarity** | 0.15 | Clear communication of intent |
| **verifiability** | 0.10 | Can the output be independently verified? |

These dimensions apply universally to all task types — code, research, planning, writing, documentation. The evaluator model is auto-routed: Sonnet for simple tasks, Opus for complex ones.

---

## Evolution System

The evolution manager triggers automatically every 2 evaluations per harness (or manually via `/adaptive-harness:evolve`). It runs three analysis phases:

### Phase 1-2: Performance Trend Analysis and Pattern Recognition

| Proposal Type | What it does | Example |
|---------------|-------------|---------|
| **Content modification** | Adds/modifies steps in `skill.md` or `agent.md` | "Add error handling review step to tdd-driven" |
| **Contract modification** | Adjusts trigger conditions | "Restrict rapid-prototype to local blast radius" |
| **Promotion / Demotion** | Moves harnesses between pools | "Promote after 5 consecutive successes" |

### Phase 3: Cross-Harness Pattern Recognition

Reads evaluation logs across **all** harnesses to detect systemic patterns:

- **Workflow gaps** — a task profile that no existing harness handles well (3+ failures across different harnesses)
- **Repeated chains** — a chain combination used 5+ times that should be consolidated into one harness
- **Complementary weaknesses** — two harnesses whose strengths/weaknesses are exact opposites (hybrid candidate)
- **Manual retries** — the same task reappears with a different harness (first selection was wrong)

### Phase 4: Concept-Level Reasoning (Pattern-Driven Genesis)

Instead of just combining existing harnesses, the evolution manager reasons about **workflow design principles** using a pattern library (`patterns/`):

```
Observed symptoms → Match failure signatures → Score pattern candidates → Generate principled harness
```

14 documented workflow patterns, all instantiated as harnesses:

| Pattern | Category | Existing Harness |
|---------|----------|-----------------|
| converge-loop | iterative | ralph-loop |
| red-green-refactor | test-driven | tdd-driven |
| hypothesis-cycle | scientific | research-iteration |
| mikado-method | structural | careful-refactor |
| plan-then-execute | deliberative | ralplan-consensus |
| multi-lens-review | verification | code-review |
| checkpoint-migrate | migration | migration-safe |
| scope-and-sprint | rapid | rapid-prototype |
| reproduce-hypothesize-verify | diagnostic | systematic-debugging |
| bisect-and-isolate | diagnostic | systematic-debugging |
| progressive-refinement | iterative | progressive-refinement *(experimental)* |
| divide-and-conquer | decomposition | divide-and-conquer *(experimental)* |
| adversarial-review | verification | adversarial-review *(experimental)* |
| spike-then-harden | two-phase | spike-then-harden *(experimental)* |

When evaluation data shows failure signatures matching a pattern, the evolution manager generates a **pattern-driven genesis proposal** — a complete new harness grounded in workflow design theory, not ad-hoc combination.

### Lifecycle

```
Eval accumulates → evolution-manager analyzes (Phase 1→2→3→4→5)
  → writes proposal JSON (status: pending)
    → next session start applies it (harness created in experimental pool)
      → router selects it with 20% exploration rate
        → 5 consecutive successes → promoted to stable
```

All proposals go to the experimental pool first. Promotion to stable requires 5 consecutive successful evaluations.

### Evolution in Action

Here's what `/adaptive-harness:evolve` actually produces after a few sessions:

```
tdd-driven — verifiability: 0.725 avg (2 runs, both low)

  Root cause:  Harness runs tests and coverage but never captures output.
               Evaluator finds empty evidence files — can't confirm results.

  Fix:         Add step "Capture verification evidence"
               → re-run tests/coverage/build with verbose output, record stdout/stderr
```

```
careful-refactor — completeness: 0.82, quality: 0.80 (repo-wide refactor)

  Root cause:  Mikado method maps code call-sites but ignores .md and .yaml files.
               Stale references survive the refactor.

  Fix:         Add "Secondary Concerns Sweep" phase
               → grep docs for stale identifiers, check config format consistency
```

Each fix is applied as an experimental variant that competes with the original. 5 consecutive wins → auto-promoted to stable.

---

## Why adaptive-harness?

| | Static skills | Manual orchestration | **adaptive-harness** |
|---|---|---|---|
| Workflow selection | Fixed | You decide | **Auto-routed** |
| Quality measurement | None | Ad-hoc | **6-dimension scoring** |
| Improvement over time | None | None | **Self-evolving** |

adaptive-harness doesn't replace your existing tools — it's a **meta-layer** that orchestrates them and learns which workflows work best in *your* codebase.

---

## Project Structure

```
agents/                 # Agent personas (Claude Code agent registry)
  router.md             #   Task classifier + harness selector
  evaluator.md          #   Result scorer (6-dimension)
  evolution-manager.md  #   Proposes harness improvements
  tdd-driven.md         #   One agent file per harness
  ...
harnesses/              # Harness workflows and contracts
  tdd-driven/
    skill.md            #   Step-by-step workflow
    contract.yaml       #   Triggers, cost budget, failure modes
    metadata.json       #   Pool state
  experimental/         #   Evolution-generated variants
    tdd-driven-v1.1/
      agent.md          #   Experimental variants keep agent.md locally
      skill.md
      ...
patterns/               # Workflow design patterns for genesis
hooks/                  # Session lifecycle hooks
skills/                 # Orchestration skills (SKILL.md files)
commands/               # Slash commands (/run, /evolve, /status, /init, /eval)
docs/                   # Architecture and design documentation
```

Agent personas live in `agents/` (registered in the Claude Code agent registry). Harness workflows, contracts, and metadata live in `harnesses/{name}/`. This separation ensures agents are discoverable by Claude Code while keeping workflow details with the harness.

---

## Contributing

adaptive-harness grows through community contributions — all in pure markdown, no code required:

- **Harnesses** — new execution workflows: agent in `agents/your-name.md`, workflow in `harnesses/your-name/`
- **Patterns** — workflow design patterns for evolution genesis (`patterns/your-name.yaml`)
- **Fixtures** — reproducible benchmark scenarios (`fixtures/your-name/`)

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

---

## Acknowledgments

Built on ideas from **[oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode)** (multi-agent orchestration) and **[superpowers](https://github.com/nicobailon/superpowers)** (skills-as-harness). The concept of harness engineering was formalized by [Martin Fowler](https://martinfowler.com/articles/exploring-gen-ai/harness-engineering.html) — adaptive-harness makes it self-improving.

## License

MIT — see [LICENSE](LICENSE).
