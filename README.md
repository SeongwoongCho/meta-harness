<p align="center">
  <h1 align="center">meta-harness</h1>
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

> **Unlike static skill packs, meta-harness gets smarter the more you use it.**

```
You: Fix the login bug where empty email crashes the server

[meta-harness]
  Classified:  bugfix | low uncertainty | local | backend
  Selected:    tdd-driven (score 0.92)  >  systematic-debugging (0.81)

[tdd-driven subagent]
  1. Write failing test for empty-email path   ✓
  2. Implement null guard in validateEmail()   ✓
  3. Run test suite (47/47 pass)               ✓

[evaluator]
  build: 1.00 | tests: 1.00 | quality: 0.91 | robustness: 0.88
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
│  4. Evaluate    protocol scoring    │
│  5. Evolve      update weights      │
└─────────────────────────────────────┘
```

**Two levels of self-improvement:**

| Level | What improves | How |
|-------|--------------|-----|
| **Routing** | Which harness gets picked | Weights adjust after every evaluation |
| **Content** | What the harness actually does | Evolution manager rewrites `agent.md`/`skill.md` via A/B testing |

Hard tasks (`uncertainty=high`) automatically trigger **ensemble mode** — two harnesses run in parallel, a synthesizer merges the best of both.

---

## Installation

```bash
claude plugin marketplace add https://github.com/SeongwoongCho/meta-harness
claude plugin install meta-harness@meta-harness
```

Then start a new Claude Code session.

---

## Quick Start

```bash
cd your-project
claude                              # new session — hooks load automatically
```

```
/meta-harness:init --general        # one-command setup with sensible defaults
```

That's it. Every task is now routed through the meta-harness pipeline automatically.

```
# Or run explicitly with options
/meta-harness:run "Refactor the payment module"
/meta-harness:run --interview "Build a new feature"
/meta-harness:run --harness=tdd-driven "Fix the login bug"
```

---

## Built-in Harnesses

| Harness | Best For | Model |
|---------|----------|-------|
| **tdd-driven** | Bugs & features with clear test expectations | Sonnet |
| **systematic-debugging** | Root cause analysis of complex bugs | Sonnet |
| **rapid-prototype** | Fast MVP when latency matters | Sonnet |
| **research-iteration** | Exploratory research with unclear requirements | Opus |
| **careful-refactor** | Safe structural refactoring (Mikado method) | Sonnet |
| **code-review** | Multi-perspective review with automated security scans | Opus |
| **migration-safe** | Dependency upgrades and migrations | Sonnet |
| **ralplan-consensus** | Upfront planning with self-review | Opus |
| **ralph-loop** | Persistent execution until acceptance criteria pass | Sonnet |

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
| `domain` | backend / frontend / ml-research / infra / docs |

---

## Evaluation Protocols

| Protocol | Best For |
|----------|----------|
| **code-quality-standard** | General code tasks (bugfix, feature, refactor, migration) |
| **research-standard** | Codebase analysis, architecture research, tech evaluation |
| **ml-research** | ML model training, fine-tuning, benchmarking |
| **web-app-performance** | Web applications |
| **cli-tool-ux** | CLI tools |

Protocols are **task-type-aware**: `code-quality-standard` automatically adjusts dimension weights per task type (e.g. research tasks de-weight `build_success` and add `analysis_depth`). The evaluator model is auto-routed — Sonnet for simple tasks, Opus for complex ones.

Custom dimensions (e.g. `api_response_time`, `model_accuracy`) are fully supported via `config.yaml`.

---

## Why meta-harness?

| | Static skills | Manual orchestration | **meta-harness** |
|---|---|---|---|
| Workflow selection | Fixed | You decide | **Auto-routed** |
| Quality measurement | None | Ad-hoc | **Protocol scoring** |
| Improvement over time | None | None | **Self-evolving** |

meta-harness doesn't replace your existing tools — it's a **meta-layer** that orchestrates them and learns which workflows work best in *your* codebase.

---

## Contributing

meta-harness grows through community contributions — all in pure markdown, no code required:

- **Harnesses** — new execution workflows (`harnesses/your-name/`)
- **Protocols** — domain-specific scoring criteria (`protocols/your-name/`)
- **Fixtures** — reproducible benchmark scenarios (`fixtures/your-name/`)

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

---

## Acknowledgments

Built on ideas from **[oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode)** (multi-agent orchestration) and **[superpowers](https://github.com/nicobailon/superpowers)** (skills-as-harness). The concept of harness engineering was formalized by [Martin Fowler](https://martinfowler.com/articles/exploring-gen-ai/harness-engineering.html) — meta-harness makes it self-improving.

## License

MIT — see [LICENSE](LICENSE).
