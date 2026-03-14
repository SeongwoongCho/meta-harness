# meta-harness Architecture

## Overview

meta-harness is a Claude Code plugin implementing a five-stage self-improving orchestration
pipeline. It intercepts every task, routes it to the optimal execution workflow (harness),
evaluates the result, and evolves its harness pool over time.

---

## 5-Stage Lifecycle

```
┌─────────────────────────────────────────────────────────────────┐
│  Stage 1: INITIALIZATION                                        │
│                                                                 │
│  SessionStart hook fires                                        │
│    → session-start.sh injects using-meta-harness-default       │
│       SKILL.md as additionalContext                             │
│    → Harness pool state loaded on-demand (not at session start) │
│    → .meta-harness/config.yaml read if present                  │
└──────────────────────────────┬──────────────────────────────────┘
                               │ User submits task
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 2: DECISION                                              │
│                                                                 │
│  Orchestrator (SKILL.md in main context) receives task          │
│    → Spawns router agent                                        │
│       Input: task description + harness pool state             │
│       Output: 6-axis taxonomy + selected harness + reasoning   │
│    → If skip_routing: true → execute directly (fast path)       │
│    → Decision Engine checks ensemble conditions                 │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                    ┌──────────┴──────────┐
                    │                     │
              ensemble=false         ensemble=true
                    │                     │
                    ▼                     ▼
┌───────────────────────┐   ┌─────────────────────────────────────┐
│  Stage 3a: SINGLE     │   │  Stage 3b: ENSEMBLE (conditional)   │
│  EXECUTION            │   │                                     │
│                       │   │  Trigger: uncertainty=high AND      │
│  Spawn one harness    │   │  (verifiability=hard OR             │
│  subagent with        │   │   blast_radius=repo-wide)           │
│  agent.md + skill.md  │   │                                     │
│  injected             │   │  Spawn 2+ harness subagents         │
│                       │   │  in parallel                        │
│                       │   │  → Spawn synthesizer agent          │
│                       │   │  → Merge results                    │
└───────────┬───────────┘   └──────────────┬──────────────────────┘
            │                              │
            └──────────────┬───────────────┘
                           │ Subagent(s) complete
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 4: EVALUATION                                            │
│                                                                 │
│  Evidence collected via PostToolUse hook (Bash commands)        │
│  Evaluator agent spawned with:                                  │
│    - Task results                                               │
│    - Evidence files (build/test/lint output)                    │
│  Evaluator produces:                                            │
│    - Per-dimension scores                                       │
│    - Overall weighted score                                     │
│    - Quality gate pass/fail                                     │
│    - Improvement suggestions                                    │
│  Result written: .meta-harness/sessions/{id}/eval-{timestamp}.json     │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 5: UPDATE (Self-Learning)                                │
│                                                                 │
│  REAL-TIME (within session):                                    │
│    - Orchestrator updates in-memory harness weights             │
│    - Better-performing harness for this task shape gets         │
│      higher weight for future routing decisions                 │
│                                                                 │
│  NEXT-SESSION (on Stop hook):                                   │
│    - session-end.sh merges in-memory weights → harness-pool.json│
│    - Evolution Manager (if triggered) proposes content changes  │
│    - Proposals written to .meta-harness/evolution-proposals/           │
│    - Applied to experimental pool; stable pool unchanged        │
│                                                                 │
│  PROMOTION:                                                     │
│    - Experimental harness → stable after N consecutive passes  │
│      (default N=5, configurable)                                │
│  DEMOTION:                                                      │
│    - Stable harness demoted if avg_score drops below threshold  │
│    - Previous version restored from git history                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Hook Lifecycle Diagram

```
Claude Code Session
│
├─ SessionStart
│   └─ hooks/session-start.sh
│       Action: Output additionalContext containing SKILL.md content
│       Injects: using-meta-harness-default/SKILL.md
│       Size target: < 3 KB (context window efficiency)
│
├─ UserPromptSubmit (fires on EVERY user message)
│   └─ hooks/prompt-interceptor.sh
│       Action: Output brief system-reminder reinforcing routing protocol
│       Size target: < 500 bytes (minimal footprint)
│       Purpose: Ensure multi-turn sessions maintain routing behavior
│
├─ PostToolUse (matcher: "Bash")
│   └─ hooks/collect-evidence.sh
│       Action: Capture Bash stdout/stderr → evidence JSON
│       Output path: .meta-harness/sessions/{session-id}/evidence/{timestamp}.json
│       Captures: build output, test results, lint results, exit codes
│       Session ID: $CLAUDE_SESSION_ID or from .meta-harness/.current-session-id
│
├─ SubagentStop (matcher: "*")
│   └─ hooks/subagent-complete.sh
│       Action: Record completion; output additionalContext reminding
│              orchestrator to check if this was a harness subagent
│              and trigger evaluation pipeline
│
└─ Stop (session end)
    └─ hooks/session-end.sh
        Action: Merge per-session weight updates into harness-pool.json
        Atomicity: write to harness-pool.json.tmp → mv (atomic rename)
        Backup: preserve harness-pool.json.bak before each write
        Cleanup: remove session directories older than 30 days
```

---

## Evaluation

All tasks are scored on 6 fixed dimensions with fixed weights:

| Dimension | Weight |
|-----------|--------|
| correctness | 0.25 |
| completeness | 0.20 |
| quality | 0.20 |
| clarity | 0.15 |
| robustness | 0.10 |
| verifiability | 0.10 |

These dimensions are hardcoded in the evaluator agent and apply universally to all task types.

---

## State Management

### Concurrency Strategy

meta-harness sessions can run concurrently (multiple Claude Code windows). The state design
prevents corruption:

```
Session A writes to:  .meta-harness/sessions/session-A/
Session B writes to:  .meta-harness/sessions/session-B/

On Stop hook:
  Session A runs session-end.sh:
    1. Read harness-pool.json
    2. Merge session-A/weights.json into pool
    3. Write to harness-pool.json.tmp
    4. mv harness-pool.json harness-pool.json.bak
    5. mv harness-pool.json.tmp harness-pool.json  ← atomic rename

  Session B runs session-end.sh (slightly later):
    Same process — reads the already-merged pool, adds its own updates
```

The `mv` rename is atomic on POSIX filesystems. If two sessions end simultaneously,
one rename wins and the other's merge reads the winning state. Net effect: all weight
updates are eventually applied; the worst case is one session's updates overwriting the
other's, not corruption.

### State File Schema

**`.meta-harness/harness-pool.json`:**
```json
{
  "version": "1.0.0",
  "last_updated": "ISO-8601 timestamp",
  "harnesses": {
    "harness-name": {
      "pool": "stable | experimental",
      "weight": 1.0,
      "successes": 0,
      "failures": 0,
      "total_runs": 0,
      "consecutive_successes": 0,
      "avg_score": 0.0
    }
  }
}
```

**`.meta-harness/sessions/{id}/eval-{timestamp}.json`:**
```json
{
  "session_id": "string",
  "timestamp": "ISO-8601",
  "task_summary": "string",
  "taxonomy": { "task_type": "...", "uncertainty": "...", ... },
  "selected_harness": "harness-name",
  "ensemble": false,
  "scores": {
    "correctness": 1.0,
    "completeness": 0.95,
    "quality": 0.88,
    "overall": 0.91
  },
  "quality_gate_passed": true,
  "improvement_suggestions": ["string"]
}
```

### Corruption Recovery

On every read of `harness-pool.json`:
1. Parse JSON — if parse fails, log warning and restore from `.bak`
2. Validate schema (version field, harnesses object present) — if invalid, re-initialize
   from built-in defaults
3. If `.bak` also corrupt, re-initialize from built-in defaults (weights reset to 1.0)

Weight loss from re-initialization is acceptable for v1. Evaluation logs in
`.meta-harness/evaluation-logs/` are the authoritative history and can be used to reconstruct
weights if needed.

---

## Evolution Loop

```
Evaluation logs accumulate
         │
         ▼ (triggered by /meta-harness-evolve or automatic threshold)
evolution-manager agent analyzes:
  - Last N evaluation results per harness
  - Performance trends (improving / stable / declining)
  - Comparison: this harness vs. alternatives on same task shapes
         │
         ▼
Proposals written to: .meta-harness/evolution-proposals/{id}.json
  Each proposal contains:
  - Target harness name
  - Change type: modify_skill | modify_agent | modify_contract
  - Proposed diff (new file content)
  - Reasoning and evidence
  - Confidence score
         │
         ▼ (applied after user review or automatically if aggressiveness=aggressive)
Changes written to: harnesses/{name}-experimental/ (new directory)
  NOT to the stable harness directory
         │
         ▼
Experimental harness enters the pool with weight=0.8
  Competes with stable version on matching tasks
         │
         ▼ After N consecutive successes (default: 5)
Promoted to stable pool:
  harnesses/{name}/ updated with experimental content
  harnesses/{name}-experimental/ removed
  Old stable version archived in git history (rollback available)
         │
         ▼ If score drops below demotion threshold
Demoted: revert to previous stable version from git history
```

---

## Agent Responsibilities

| Agent | Model | Inputs | Outputs |
|-------|-------|--------|---------|
| **router** | Sonnet | Task description, harness pool state | Taxonomy JSON, selected harness, ensemble flag, reasoning |
| **evaluator** | Opus | Task results, evidence files | Dimension scores, overall score, quality gate, suggestions |
| **synthesizer** | Opus | Multiple subagent results with scores | Merged result, score comparison, merge reasoning |
| **evolution-manager** | Opus | Evaluation history, current harness files | Evolution proposals as file diffs |

---

## Plugin System Constraints

These are hard constraints imposed by Claude Code's plugin architecture:

1. **Subagents cannot spawn subagents** — The orchestrator (SKILL.md running in main
   context) handles all agent fan-out. Harness subagents cannot spawn evaluator agents.

2. **Hooks snapshot at session start** — Hook scripts are loaded once at `SessionStart`.
   Harness content changes (evolution) take effect at the next session start, not
   mid-session.

3. **`UserPromptSubmit` hook fires per message** — Used for multi-turn routing
   reinforcement. Each new task in a session goes through the routing pipeline.

4. **No MCP server required** — All state management uses file-based atomic writes.
   An MCP server may be introduced in v2 if concurrent-session corruption becomes a
   practical issue.

---

## Known Limitations (v1)

| Limitation | Impact | Planned Fix |
|------------|--------|-------------|
| Session crash before Stop hook | In-session weight updates lost | Evaluation logs survive; weights reconstructable |
| Simultaneous Stop hooks (concurrent sessions) | One session's merge may overwrite another's | Acceptable for v1; v2 MCP server would solve this |
| Router adds 5–15s latency per task | Overhead on every task | Fast-path (`skip_routing: true`) for trivial follow-ups |
| Ensemble doubles token cost | Expensive for high-volume use | Conditional trigger + `ensemble.enabled: false` in config |
