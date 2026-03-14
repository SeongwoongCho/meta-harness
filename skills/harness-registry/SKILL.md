---
name: harness-registry
description: "Manage the meta-harness pool: list, inspect, promote, demote harnesses. Use when user asks about harness status or wants to manage the pool."
---

# Harness Registry

## Purpose

You manage the meta-harness harness pool. Use this skill when the user asks about harness status, wants to inspect a specific harness, or wants to promote/demote harnesses between stable and experimental pools.

---

## Operations

### List All Harnesses

Read `state/harness-pool.json` and display all harnesses with their pool status and performance stats:

```
Read("state/harness-pool.json")
```

Display format:
```
STABLE POOL
  tdd-driven          weight=1.02  successes=14  failures=2   runs=16
  systematic-debugging weight=0.98  successes=9   failures=3   runs=12
  rapid-prototype     weight=1.05  successes=21  failures=1   runs=22
  careful-refactor    weight=0.95  successes=7   failures=4   runs=11
  research-iteration  weight=1.00  successes=5   failures=0   runs=5
  code-review         weight=1.01  successes=18  failures=1   runs=19
  migration-safe      weight=0.99  successes=6   failures=1   runs=7

EXPERIMENTAL POOL
  (none)
```

If `state/harness-pool.json` does not exist, report that no state has been initialized and suggest running `/meta-harness-init`.

### Inspect a Specific Harness

When user asks "inspect {harness-name}" or "show me the {harness-name} harness":

Read and display:
- `harnesses/{name}/agent.md` — agent persona
- `harnesses/{name}/skill.md` — workflow
- `harnesses/{name}/contract.yaml` — execution contract
- `harnesses/{name}/metadata.json` — current pool status and stats

Present in a structured format showing trigger conditions, tool policy, stopping criteria, cost budget, and failure modes.

### Promote Experimental → Stable

When user says "promote {harness-name}" or when queried about a harness meeting promotion criteria:

1. Read `state/harness-pool.json`
2. Check the harness's `consecutive_successes` count (requires ≥5 by default, configurable in `.meta-harness/config.yaml` under `evolution_settings.promotion_threshold`)
3. If criteria met:
   - Update `harnesses/{name}/metadata.json`: set `"pool": "stable"`
   - Update `state/harness-pool.json`: move entry from `experimental` to `stable`
   - Write atomically: write to `state/harness-pool.json.tmp` then rename to `state/harness-pool.json`
   - Create backup `state/harness-pool.json.bak` before writing
4. Report: "Promoted {name} from experimental to stable pool. Consecutive successes: N."

### Demote Stable → Experimental

When user says "demote {harness-name}" or when a harness performance drops below threshold:

1. Check the harness's recent performance (last 10 runs from evaluation logs in `state/evaluation-logs/{harness-name}/`)
2. If performance below threshold (default: score < 0.5 for 3+ consecutive runs):
   - Update `harnesses/{name}/metadata.json`: set `"pool": "experimental"`
   - Update `state/harness-pool.json`: move entry from `stable` to `experimental`
   - Write atomically (same pattern as promote)
   - Record demotion event in `state/evaluation-logs/{name}/demotion-{timestamp}.json`
3. Report: "Demoted {name} to experimental pool. Recent scores: [0.42, 0.38, 0.41]."

### Check Promotion Eligibility

When user asks "which harnesses are ready for promotion":

1. Read `state/harness-pool.json`
2. For each experimental harness, check `consecutive_successes` against threshold
3. List eligible harnesses and their stats
4. Suggest running promotion for eligible ones

---

## Pool State Schema

`state/harness-pool.json` structure:
```json
{
  "version": "1.0",
  "updated_at": "2026-03-14T12:00:00Z",
  "stable": {
    "tdd-driven": {
      "weight": 1.02,
      "successes": 14,
      "failures": 2,
      "total_runs": 16,
      "consecutive_successes": 3,
      "last_run": "2026-03-14T11:55:00Z"
    }
  },
  "experimental": {
    "custom-harness": {
      "weight": 1.0,
      "successes": 2,
      "failures": 1,
      "total_runs": 3,
      "consecutive_successes": 2,
      "last_run": "2026-03-14T10:00:00Z"
    }
  }
}
```

---

## Atomic Write Pattern

Always use atomic writes when modifying `state/harness-pool.json`:

```bash
# Write to temp, then atomically rename
cp state/harness-pool.json state/harness-pool.json.bak
# Write new content to state/harness-pool.json.tmp
# Then: mv state/harness-pool.json.tmp state/harness-pool.json
```

Use a Bash tool call for the atomic rename step.
