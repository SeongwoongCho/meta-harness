---
description: "Show meta-harness pool state, performance stats, and evolution history"
---

# meta-harness-status

Display the current state of the meta-harness pool including harness performance statistics, pool membership, recent evaluation history, and pending evolution proposals.

## Execution Steps

### Step 1: Read Pool State and Pipeline Mode

```
Read(".meta-harness/harness-pool.json")
Read(".meta-harness/config.yaml")
Bash("cat .meta-harness/.pipeline-mode 2>/dev/null || echo 'off'")
```

If `.meta-harness/harness-pool.json` does not exist:
```
meta-harness has not been initialized for this project.
Run /meta-harness-init to set up the harness pool.
```

### Step 2: Read Recent Evaluation Logs

Scan `.meta-harness/sessions/` for the most recent 10 evaluation files across all sessions:
```
Glob(".meta-harness/sessions/*/eval-*.json")
```

Read each and extract: harness name, overall score, timestamp, quality gate pass/fail.

Also check for pending evolution proposals:
```
Glob(".meta-harness/evolution-proposals/*.json")
```

### Step 3: Display Status

Format and display the full status report:

```
═══════════════════════════════════════════════
  META-HARNESS STATUS
  Project: {domain} | Protocol: {default_protocol}
  Pipeline mode: {auto|run|off}
  Pool initialized: {initialized_at}
═══════════════════════════════════════════════

STABLE POOL ({N} harnesses)
┌─────────────────────────┬────────┬────────┬──────────┬────────────┐
│ Harness                 │ Weight │  Runs  │  Score   │ Last Run   │
├─────────────────────────┼────────┼────────┼──────────┼────────────┤
│ tdd-driven              │  1.02  │   16   │  0.87    │ 2026-03-14 │
│ systematic-debugging    │  0.98  │   12   │  0.81    │ 2026-03-13 │
│ rapid-prototype         │  1.05  │   22   │  0.91    │ 2026-03-14 │
│ careful-refactor        │  0.95  │   11   │  0.78    │ 2026-03-12 │
│ research-iteration      │  1.00  │    5   │  0.84    │ 2026-03-10 │
│ code-review             │  1.01  │   19   │  0.88    │ 2026-03-14 │
│ migration-safe          │  0.99  │    7   │  0.83    │ 2026-03-11 │
└─────────────────────────┴────────┴────────┴──────────┴────────────┘

EXPERIMENTAL POOL ({N} harnesses)
  (none) — Add custom harnesses to harnesses/ to see them here.

RECENT EVALUATIONS (last 10)
  2026-03-14 14:32  tdd-driven        0.89  PASS   "Fix auth login bug"
  2026-03-14 11:15  rapid-prototype   0.93  PASS   "Add dark mode toggle"
  2026-03-13 16:44  careful-refactor  0.76  PASS   "Extract shared utils"
  ...

EVOLUTION PROPOSALS
  {N pending proposals — run /meta-harness-evolve to review}
  OR
  No pending proposals.

CONFIGURATION
  Domain:              {domain}
  Default protocol:    {default_protocol}
  Pipeline mode:       {auto|run|off}
  Ensemble mode:       {auto|always|never}
  Evolution:           {enabled (threshold: N successes) | disabled}
  Config file:         .meta-harness/config.yaml

PIPELINE MODE INFO
  auto  — All tasks auto-routed (using-meta-harness-default active)
  run   — One-shot /meta-harness:run in progress
  off   — No auto-routing (use /meta-harness:run for explicit runs)

  Toggle: printf 'auto' > .meta-harness/.pipeline-mode   (enable)
          rm -f .meta-harness/.pipeline-mode              (disable)
```

### Step 4: Highlight Actionable Items

After the main display, show any alerts:

**Demotion candidates** (stable harnesses with poor recent performance):
```
  ALERT: careful-refactor has scored below 0.6 for 3 consecutive runs.
         Consider demoting: /harness-registry demote careful-refactor
```

**Promotion candidates** (experimental harnesses meeting threshold):
```
  READY: custom-harness has {N} consecutive successes.
         Ready to promote: /harness-registry promote custom-harness
```

**No evaluations yet:**
```
  No evaluation data yet. Run /meta-harness-run <task> to start collecting data.
```
