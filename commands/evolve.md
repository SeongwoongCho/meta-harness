---
description: "Trigger harness evolution: analyze evaluation logs, propose changes, apply to experimental pool"
---

# meta-harness-evolve

Trigger the harness evolution cycle. Reads evaluation history, spawns the evolution-manager agent to analyze performance patterns, and applies proposed modifications to the experimental harness pool. Promoted harnesses take effect next session.

## Execution Steps

### Step 1: Check Prerequisites

Read evaluation history:
```
Glob(".meta-harness/sessions/*/eval-*.json")
Glob(".meta-harness/evaluation-logs/**/*.json")
```

If fewer than 5 evaluation files found:
```
Not enough evaluation data to run evolution.
Current evaluations: {N} (minimum: 5)

Run more tasks via /meta-harness-run or auto-mode to collect evaluation data.
```

### Step 2: Aggregate Evaluation History

Read all evaluation files. For each harness, compile:
- Total runs, success rate, average score
- Score trend (improving/declining/stable over last 10 runs)
- Most common failure modes from `improvement_suggestions`
- Task types where this harness underperforms

Build a summary per harness:
```json
{
  "tdd-driven": {
    "total_runs": 16,
    "avg_score": 0.87,
    "trend": "stable",
    "weak_dimensions": ["robustness"],
    "common_failures": ["error handling not comprehensive"]
  }
}
```

### Step 3: Read Current Harness Files

For each harness with enough data (≥3 runs), read its current content:
```
Read("harnesses/{name}/agent.md")
Read("harnesses/{name}/skill.md")
Read("harnesses/{name}/contract.yaml")
Read("harnesses/{name}/metadata.json")
```

### Step 4: Spawn Evolution Manager Agent

```
Task(
  subagent_type="meta-harness:evolution-manager",
  prompt="Analyze harness performance and propose improvements.\n\nEvaluation summary:\n{aggregated_summary}\n\nCurrent harness files:\n{harness_file_contents}\n\nFor each underperforming harness, propose concrete modifications to agent.md, skill.md, or contract.yaml.\nWrite proposals to .meta-harness/evolution-proposals/{proposal-id}.json.\nAlso recommend promotion/demotion actions based on consecutive_successes/failures.\n\nRead .meta-harness/config.yaml for evolution thresholds."
)
```

### Step 5: Review and Apply Proposals

After the evolution manager completes, read all new proposals:
```
Glob(".meta-harness/evolution-proposals/*.json")
```

Display each proposal to the user:
```
Evolution proposal {id}:
  Harness: {harness_name}
  Type: content_modification | promotion | demotion
  Rationale: {reasoning}
  Changes:
    agent.md: {summary of changes}
    skill.md: {summary of changes}
    contract.yaml: {summary of changes}
```

Ask for confirmation before applying:
```
AskUserQuestion(
  "Apply these evolution proposals?",
  options=[
    "Apply all to experimental pool",
    "Review each individually",
    "Skip — I'll review the proposals manually in .meta-harness/evolution-proposals/"
  ]
)
```

### Step 6: Apply Approved Changes

For approved proposals:

1. **Content modifications** — Write modified files to the experimental pool directory:
   ```
   harnesses/{name}-experimental/agent.md
   harnesses/{name}-experimental/skill.md
   harnesses/{name}-experimental/contract.yaml
   harnesses/{name}-experimental/metadata.json  ← set pool: "experimental"
   ```
   Register in `.meta-harness/harness-pool.json` under `experimental`.

2. **Promotions** — Update `harnesses/{name}/metadata.json` pool field to `"stable"`. Update `.meta-harness/harness-pool.json` atomically (write to `.tmp`, rename).

3. **Demotions** — Update `harnesses/{name}/metadata.json` pool field to `"experimental"`. Log demotion event.

### Step 7: Report

```
Evolution cycle complete.

Applied {N} proposals:
  MODIFIED (experimental): tdd-driven-experimental
    — Strengthened error handling steps in skill.md
    — Added robustness verification to stopping criteria
  PROMOTED: rapid-prototype → stable
    — 6 consecutive successes (threshold: 5)
  (none demoted)

Experimental pool additions take effect next session (loaded by session-start.sh).
Promotions/demotions are effective immediately.

To monitor results: /meta-harness-status
To manually promote experimental harnesses: /harness-registry promote {name}
```

### Notes on Safety

- All content modifications go to the **experimental** pool first. They never directly overwrite stable harnesses.
- Promotion to stable requires `consecutive_successes ≥ threshold` (configurable in `.meta-harness/config.yaml`).
- Previous harness versions are preserved in git history. To roll back a harness: `git checkout HEAD~1 -- harnesses/{name}/`.
- Evolution proposals in `.meta-harness/evolution-proposals/` are never auto-deleted. Review them with a text editor anytime.
