---
description: "Trigger harness evolution: analyze evaluation logs, propose changes, apply to experimental pool"
argument-hint: "[--skip-interview]"
---

# meta-harness-evolve

Trigger the harness evolution cycle. Reads evaluation history, spawns the evolution-manager agent to analyze performance patterns, and applies proposed modifications to the experimental harness pool. Promoted harnesses take effect next session.

## Parsing Arguments

Parse `$ARGUMENTS` for flags:
- `--skip-interview` — Optional flag. If passed, auto-apply all proposals to the experimental pool without asking for user confirmation. Default behavior (without this flag) is to display each proposal and ask for confirmation before applying.

## Plugin Root

Read the plugin root path: `Read(".meta-harness/.plugin-root")`. Store as `{plugin_root}`. All plugin-internal paths use this prefix.

## Execution Steps

### Step 0: Load Evolution State

Read the evolution state file to determine which sessions have already been processed:
```
Read(".meta-harness/evolution-state.json")
```

If the file does not exist, initialize with:
```json
{
  "evolved_sessions": [],
  "evolution_memory": {}
}
```

- `evolved_sessions` — list of session IDs (or eval file names) already analyzed by a previous evolution run
- `evolution_memory` — per-harness summaries from previous evolution analyses (keyed by harness name), enabling the evolution manager to build on prior insights rather than re-analyzing from scratch

### Step 1: Check Prerequisites

Read evaluation history:
```
Glob(".meta-harness/sessions/*/eval-*.json")
Glob(".meta-harness/evaluation-logs/**/*.json")
```

**Filter out already-processed sessions**: Remove any eval files whose session ID (or filename) appears in `evolved_sessions` from the evolution state. Only pass NEW (unprocessed) evaluation data to the evolution manager.

If fewer than 2 NEW evaluation files found:
```
Not enough evaluation data to run evolution.
Current evaluations: {N} (minimum: 2)

Run more tasks via /meta-harness:run or auto-mode to collect evaluation data.
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
Read("{plugin_root}/agents/{name}.md")
Read("{plugin_root}/harnesses/{name}/skill.md")
Read("{plugin_root}/harnesses/{name}/contract.yaml")
Read("{plugin_root}/harnesses/{name}/metadata.json")
```

### Step 4: Spawn Evolution Manager Agent

Pass only NEW evaluation data (filtered in Step 1) and the `evolution_memory` from previous runs:

```
Task(
  subagent_type="meta-harness:evolution-manager",
  prompt="Analyze harness performance and propose improvements.\n\nEvaluation summary (NEW sessions only):\n{aggregated_summary}\n\nEvolution memory (summaries from previous analyses):\n{evolution_memory}\n\nCurrent harness files:\n{harness_file_contents}\n\nFor each underperforming harness, propose concrete modifications to agent.md, skill.md, or contract.yaml.\nWrite proposals to .meta-harness/evolution-proposals/{proposal-id}.json.\nAlso recommend promotion/demotion actions based on consecutive_successes/failures.\n\nRead .meta-harness/config.yaml for evolution thresholds."
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

**If `--skip-interview` was passed**, skip the confirmation step and auto-apply all proposals to the experimental pool (proceed directly to Step 6).

**Otherwise (default)**, ask for confirmation before applying:
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
   {plugin_root}/harnesses/experimental/{variant-name}/agent.md  (experimental harnesses keep agent.md locally)
   {plugin_root}/harnesses/experimental/{variant-name}/skill.md
   {plugin_root}/harnesses/experimental/{variant-name}/contract.yaml
   {plugin_root}/harnesses/experimental/{variant-name}/metadata.json  ← set pool: "experimental"
   ```
   Register in `.meta-harness/harness-pool.json` under `experimental`.

2. **Promotions** — Update `{plugin_root}/harnesses/{name}/metadata.json` pool field to `"stable"`. Update `.meta-harness/harness-pool.json` atomically (write to `.tmp`, rename).

3. **Demotions** — Update `{plugin_root}/harnesses/{name}/metadata.json` pool field to `"experimental"`. Log demotion event.

### Step 7: Report

```
Evolution cycle complete.

Applied {N} proposals:
  MODIFIED (experimental): experimental/tdd-driven-v1.1
    — Strengthened error handling steps in skill.md
    — Added robustness verification to stopping criteria
  PROMOTED: rapid-prototype → stable
    — 6 consecutive successes (threshold: 5)
  (none demoted)

Experimental pool additions take effect next session (loaded by session-start.sh).
Promotions/demotions are effective immediately.

To monitor results: /meta-harness:status
To manually promote experimental harnesses: /harness-registry promote {name}
```

### Step 8: Update Evolution State

After the evolution cycle completes (whether proposals were applied or not), update `.meta-harness/evolution-state.json`:

1. Append all newly-processed session IDs (or eval filenames) to `evolved_sessions`
2. Update `evolution_memory` with per-harness summaries from this evolution run (the evolution manager's `performance_summary` and `no_action_harnesses` fields). This allows future runs to build on accumulated insights.

```
Write(".meta-harness/evolution-state.json", {
  "evolved_sessions": [...previous_evolved_sessions, ...newly_processed_sessions],
  "evolution_memory": {
    ...previous_evolution_memory,
    "{harness_name}": {
      "last_analyzed_at": "{iso_timestamp}",
      "total_runs_at_analysis": N,
      "avg_score_at_analysis": 0.XX,
      "trend_at_analysis": "stable|improving|declining",
      "proposals_generated": ["proposal-id-1", ...],
      "notes": "summary from evolution manager"
    }
  }
})
```

### Notes on Safety

- All content modifications go to the **experimental** pool first. They never directly overwrite stable harnesses.
- Promotion to stable requires `consecutive_successes ≥ threshold` (configurable in `.meta-harness/config.yaml`).
- Previous harness versions are preserved in git history. To roll back a harness: `git checkout HEAD~1 -- harnesses/{name}/`.
- Evolution proposals in `.meta-harness/evolution-proposals/` are never auto-deleted. Review them with a text editor anytime.
