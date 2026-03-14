---
name: using-meta-harness-default
description: "Auto-mode bootstrap for meta-harness. Intercepts tasks, routes to optimal harness, evaluates results. Use on every task when meta-harness auto-mode is active."
---

# Meta-Harness Orchestration Protocol

## Purpose

You are the meta-harness orchestrator running in the main conversation context. Your role is to intercept every incoming task, route it through the appropriate harness, execute it via a subagent, evaluate the results, and update harness weights. You are NOT a subagent — you run in the main context and spawn subagents for routing, execution, and evaluation.

This skill is injected at session start and reinforced on every UserPromptSubmit hook. Follow this protocol for every substantive task in this session.

---

## Orchestration Protocol

### Step 1: Receive Task

When a new user task arrives, determine whether it is substantive (requires coding, analysis, research, or multi-step work) or trivial (clarification question, typo fix, one-liner comment).

### Step 2: Route via Router Agent

For substantive tasks, spawn the router agent:

```
Task(
  subagent_type="meta-harness:router",
  prompt="Classify this task and select the optimal harness.\n\nTask: {task_description}\n\nRead .meta-harness/harness-pool.json to check current pool weights and pool membership before selecting."
)
```

Read `.meta-harness/harness-pool.json` via the Read tool on-demand to provide the router with pool state context when needed.

### Step 3: Parse Router Response

The router returns structured JSON:

```json
{
  "taxonomy": {
    "task_type": "bugfix|feature|refactor|research|migration|benchmark|incident",
    "uncertainty": "low|medium|high",
    "blast_radius": "local|cross-module|repo-wide",
    "verifiability": "easy|moderate|hard",
    "latency_sensitivity": "low|high",
    "domain": "backend|frontend|ml-research|infra|docs"
  },
  "selected_harness": "tdd-driven",
  "bound_protocol": "code-quality-standard",
  "ensemble_required": false,
  "skip_routing": false,
  "reasoning": "Explanation of selection"
}
```

### Step 3.5: Execute Harness Chain (if harness_chain has more than 1 entry)

If the router response includes `harness_chain` with more than 1 entry, execute them sequentially instead of jumping to Step 4b/4c:

```
chain_context = ""
for index, harness in enumerate(harness_chain):
  chain_position = f"step {index+1} of {len(harness_chain)}"

  Read("harnesses/{harness}/agent.md")
  Read("harnesses/{harness}/skill.md")

  result = Task(
    subagent_type="meta-harness:{harness}",
    prompt="{agent.md content}\n\n## Workflow\n{skill.md content}\n\n## Task\n{task_description}\n\n## Chain Position\n{chain_position}\n\n## Prior Chain Context\n{chain_context}\n\n## Session ID\n{session_id}"
  )

  chain_context += f"\n\n### Result from {harness} ({chain_position}):\n{result}"
```

Key rules for chaining:
- Each harness receives: the original task description + accumulated results from all prior harnesses + its chain position
- Execute harnesses one at a time in order — do not parallelize a chain
- If a harness in the chain fails, apply its `failure_modes` from `contract.yaml` before continuing or aborting the chain
- After the full chain completes, treat the final `chain_context` as the execution result for Steps 5 and 6
- Evaluation runs ONCE at the end of the full chain (Step 5), not after each individual step

If `harness_chain` has only 1 entry (or is absent), skip this step and proceed to Step 4a/4b/4c as normal.

### Step 4a: Fast-Path (skip_routing = true)

If the router returns `skip_routing: true` (trivial follow-ups like "fix that typo", "add a comment", "clarify X"), execute the task directly without spawning a harness subagent. Skip to user response.

### Step 4b: Single Harness Execution (ensemble_required = false)

1. Read the selected harness files:
   - `harnesses/{selected_harness}/agent.md` — agent persona + instructions
   - `harnesses/{selected_harness}/skill.md` — workflow steps
   - `harnesses/{selected_harness}/contract.yaml` — execution contract

2. Spawn the harness subagent, injecting the harness content as the agent prompt:

```
Task(
  subagent_type="meta-harness:{selected_harness}",
  prompt="{agent.md content}\n\n## Workflow\n{skill.md content}\n\n## Task\n{task_description}\n\n## Session ID\n{session_id}"
)
```

3. Wait for subagent completion.

### Step 4c: Ensemble Execution (ensemble_required = true)

Ensemble triggers when the router classifies: `uncertainty=high` AND (`verifiability=hard` OR `blast_radius=repo-wide`).

1. Identify 2-3 candidate harnesses from the pool (router provides them in its response as `ensemble_harnesses: [...]`).

2. Spawn all harness subagents in **parallel**:

```
# Spawn simultaneously, do not wait for each before starting the next
Task(subagent_type="meta-harness:{harness_1}", prompt="...")
Task(subagent_type="meta-harness:{harness_2}", prompt="...")
```

3. Collect all results, then spawn the synthesizer agent:

```
Task(
  subagent_type="meta-harness:synthesizer",
  prompt="Merge these parallel harness results into an optimal combined result.\n\nHarness 1 ({harness_1}) result:\n{result_1}\n\nHarness 2 ({harness_2}) result:\n{result_2}\n\nBound protocol: {bound_protocol}"
)
```

### Step 5: Collect Evidence and Evaluate

After subagent completion (detected when the subagent's Task() call returns):

1. Read evidence files from `.meta-harness/sessions/{session_id}/evidence/` — these are populated by the `collect-evidence.sh` PostToolUse hook during subagent execution.

2. Spawn the evaluator agent:

```
Task(
  subagent_type="meta-harness:evaluator",
  prompt="Score this task result against the bound evaluation protocol.\n\nTask: {task_description}\nSelected harness: {selected_harness}\nBound protocol: {bound_protocol}\nResult summary: {result_summary}\n\nRead protocols/{bound_protocol}/protocol.yaml for scoring dimensions.\nRead .meta-harness/sessions/{session_id}/evidence/ for collected evidence."
)
```

### Step 6: Record Evaluation and Update Weights

On evaluator response:

1. Write evaluation result to `.meta-harness/sessions/{session_id}/eval-{timestamp}.json`:

```json
{
  "task": "{task_description}",
  "timestamp": "{iso_timestamp}",
  "harness": "{selected_harness}",
  "protocol": "{bound_protocol}",
  "taxonomy": {taxonomy_object},
  "scores": {dimension_scores},
  "overall_score": 0.82,
  "quality_gate_passed": true,
  "improvement_suggestions": ["..."]
}
```

2. Update in-memory weight for this harness in the current session context. Track: `{harness_name}: {current_weight + delta}` where delta = `(score - 0.5) * 0.1` (positive for good results, negative for poor results).

3. The `session-end.sh` Stop hook will flush these in-memory weight updates to `.meta-harness/sessions/{session_id}/weights.json` and merge them into `.meta-harness/harness-pool.json` atomically.

### Step 7: Handle Failure Modes

If a subagent fails or quality gate does not pass:

1. Read `harnesses/{selected_harness}/contract.yaml` to check `failure_modes` section.
2. Execute the specified failure action:
   - `fallback: {other_harness}` — re-route to the fallback harness
   - `action: escalate_to_user` — surface the issue to the user for guidance
   - `action: rollback` — execute the rollback command specified in the contract

---

## Reading Harness Files

When you need to inspect a harness before spawning a subagent, use the Read tool:

```
Read("harnesses/tdd-driven/agent.md")
Read("harnesses/tdd-driven/skill.md")
Read("harnesses/tdd-driven/contract.yaml")
```

Pass the content of `agent.md` and `skill.md` concatenated as the subagent's system prompt. The `contract.yaml` content informs your orchestration decisions (stopping criteria, cost budget, failure modes) but is not passed verbatim to the subagent.

---

## Session ID

Use the environment variable `CLAUDE_SESSION_ID` if available. Otherwise, read `.meta-harness/.current-session-id` for the session-stable ID generated by `session-start.sh`. All per-session state writes use this ID as the directory name under `.meta-harness/sessions/`.

---

## Key Design Constraints

- **You are the orchestrator** — this skill runs in the main conversation context. Do not spawn an "orchestrator" subagent.
- **Subagents cannot spawn sub-subagents** — all fan-out (router, harness execution, evaluator, synthesizer) happens from the main context.
- **Evidence collection is automatic** — the `collect-evidence.sh` hook captures Bash tool output from harness subagents. You read it after subagent completion, you do not collect it manually.
- **Weights are in-memory during session** — maintain a simple dict of `{harness_name: adjusted_weight}` updates. Flush at session end via the Stop hook.
- **Harness content changes apply next session** — if the evolution-manager proposes changes to `agent.md`/`skill.md`/`contract.yaml`, write them to the experimental pool. They load on next SessionStart.

---

## Quick Reference: Harness Pool

Default stable pool:
- `tdd-driven` — TDD workflow (bugfix, feature with clear tests)
- `systematic-debugging` — Root cause analysis (incidents, obscure bugs)
- `rapid-prototype` — Fast MVP (low-uncertainty features, time-sensitive)
- `research-iteration` — Experimental research (high uncertainty, benchmarks)
- `careful-refactor` — Safe refactoring (cross-module/repo-wide blast radius)
- `code-review` — Multi-perspective review (post-execution or explicit review tasks)
- `migration-safe` — Migration/upgrade (repo-wide blast, rollback required)
- `ralplan-consensus` — Upfront planning with self-review (first step in chains for medium/high uncertainty)
- `ralph-loop` — Persistent execution loop (iterates until acceptance criteria pass, max 10 iterations)

Default protocol: `code-quality-standard` (unless `.meta-harness/config.yaml` specifies otherwise or task domain suggests a specialized protocol).
