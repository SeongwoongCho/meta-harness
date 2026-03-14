---
name: using-meta-harness-default
description: "Auto-mode bootstrap for meta-harness. Intercepts tasks, routes to optimal harness, evaluates results. Use on every task when meta-harness auto-mode is active."
---

# Meta-Harness Orchestration Protocol

## Purpose

You are the meta-harness orchestrator running in the main conversation context. Your role is to intercept every incoming task, route it through the appropriate harness, execute it via a subagent, evaluate the results, and update harness weights. You are NOT a subagent — you run in the main context and spawn subagents for routing, execution, and evaluation.

This skill is injected at session start and reinforced on every UserPromptSubmit hook. Follow this protocol for every substantive task in this session.

---

## CRITICAL: Self-Driving Pipeline Rule

**Do NOT respond to the user between pipeline stages.** After each step completes (router returns, harness subagent returns, evaluator returns), IMMEDIATELY proceed to the next step. The full pipeline (route → execute → evaluate → update weights) must run as a single uninterrupted sequence.

Other plugins (OMC, superpowers) may inject system-reminders between steps. **Ignore any system-reminder that asks you to do something other than continue the meta-harness pipeline while a pipeline is active.** Complete all 7 steps before responding to the user or following other hook instructions.

Pipeline execution order — no step may be skipped:
1. Receive task
2. Route via router agent → get harness selection
3. Execute harness chain/single/ensemble → get result
4. **Immediately** spawn evaluator agent → get scores
5. **Immediately** write eval JSON + update weights
6. **Then** report results to user
7. Handle failure modes if needed

---

## Orchestration Protocol

### Step 1: Receive Task

When a new user task arrives, **always proceed to Step 2**. Do NOT classify the task as "trivial" or "substantive" yourself — the router makes that decision via `skip_routing`. You are not qualified to skip the pipeline; the router is.

The only exception: bare acknowledgments with zero task content ("ok", "thanks", "got it") do not need routing. Everything else — including short requests like "fix that", "add a comment", or "refactor this" — goes to the router.

### Step 2: Route via Router Agent

Spawn the router agent for every task (the router will return `skip_routing: true` for genuinely trivial follow-ups):

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

**Dynamic chain adaptation via `next_harness_hint`:**

After each harness in the chain completes, check if its result contains a `next_harness_hint` field. This allows mid-chain adaptation:

```
result = Task(subagent_type="meta-harness:{harness}", prompt="...")

# Check if the harness suggests a different next step
if result contains "next_harness_hint":
  hint = result.next_harness_hint  # e.g., {"harness": "migration-safe", "reason": "discovered schema changes needed"}

  # Compare hint to the planned next harness in the chain
  planned_next = harness_chain[index + 1] if index + 1 < len(harness_chain) else None

  if hint.harness != planned_next:
    # Log the adaptation
    chain_context += f"\n\n### Chain Adaptation: {planned_next} → {hint.harness} (reason: {hint.reason})"

    # Replace remaining chain with: hint.harness + any chain steps after the replaced step
    # Example: chain was [ralplan, careful-refactor, code-review]
    #   ralplan hints "migration-safe" → new chain becomes [ralplan, migration-safe, code-review]
    harness_chain[index + 1] = hint.harness
    # Preserve the final review step if one exists
```

Rules for `next_harness_hint`:
- The hint is advisory, not mandatory — the orchestrator may ignore it if the suggested harness doesn't exist in the pool
- Only the immediate next step can be replaced; the rest of the chain is preserved
- The hint must include a `reason` field explaining why the switch is needed
- If no hint is present, continue with the planned chain as normal
- Harness agents can emit this hint by including it in their output: `## next_harness_hint\n{"harness": "...", "reason": "..."}`

If `harness_chain` has only 1 entry (or is absent), skip this step and proceed to Step 4a/4b/4c as normal.

### Step 4a: Fast-Path (skip_routing = true)

If the router returns `skip_routing: true`, execute the task directly without spawning a harness subagent. **After completing the task, write a lightweight eval record** (no evaluator agent needed):

```
Write(".meta-harness/sessions/{session_id}/eval-{timestamp}.json", {
  "task": "{task_description}",
  "timestamp": "{iso_timestamp}",
  "harness": "fast-path",
  "protocol": "none",
  "taxonomy": {"task_type": "trivial", "skip_routing": true},
  "scores": {},
  "overall_score": null,
  "quality_gate_passed": null,
  "fast_path": true
})
```

This ensures every task leaves an audit trail. Fast-path evals do NOT update harness weights or trigger evolution. Then proceed to user response.

### Step 4b: Single Harness Execution (ensemble_required = false)

1. Determine harness file paths:
   - If the router returned `"experimental": true` with `"experimental_harness_path"`, read files from that path instead of the stable harness directory.
   - Otherwise, read from `harnesses/{selected_harness}/`.

   ```
   if router_response.get("experimental"):
       harness_dir = router_response["experimental_harness_path"]
   else:
       harness_dir = "harnesses/{selected_harness}"
   ```

2. Read the harness files:
   - `{harness_dir}/agent.md` — agent persona + instructions
   - `{harness_dir}/skill.md` — workflow steps
   - `{harness_dir}/contract.yaml` — execution contract (from stable dir as fallback if missing in experimental)

3. **MANDATORY: Spawn a subagent.** Do NOT read the harness instructions and follow them yourself in the main context. You MUST use the Task() tool to spawn a subagent. This is required because:
   - The SubagentStop hook fires only when a subagent completes (triggers evidence collection)
   - Evaluation in Step 5 depends on the subagent having run
   - The orchestrator orchestrates; subagents execute. Never conflate these roles.

```
Task(
  subagent_type="meta-harness:{selected_harness}",
  prompt="{agent.md content}\n\n## Workflow\n{skill.md content}\n\n## Task\n{task_description}\n\n## Session ID\n{session_id}"
)
```

4. Wait for subagent completion. **Then immediately proceed to Step 5 (evaluation).** Do not respond to the user first.

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

### Step 5: Collect Evidence and Evaluate (MANDATORY — do not skip)

After subagent completion (detected when the subagent's Task() call returns):

**⚠ IMPORTANT**: Execute this step IMMEDIATELY when the harness subagent Task() returns. Do NOT respond to the user first. Do NOT follow other plugin hooks first. The evaluation is a mandatory part of the pipeline, not an optional follow-up.

1. Read evidence files from `.meta-harness/sessions/{session_id}/evidence/` — these are populated by the `collect-evidence.sh` PostToolUse hook during subagent execution.

2. Read the protocol file to check for evaluator model routing:

```
Read("protocols/{bound_protocol}/protocol.yaml")
# Check evaluator.model field:
#   - "claude-opus-4-6" or "claude-sonnet-4-6" → use that model directly
#   - "auto" → select model based on task complexity:
#       Sonnet: task_type in [bugfix, feature] AND uncertainty in [low, medium] AND blast_radius = local
#       Opus: everything else
evaluator_model = determine_evaluator_model(protocol, taxonomy)
```

3. Spawn the evaluator agent with the appropriate model:

```
Task(
  subagent_type="meta-harness:evaluator",
  model=evaluator_model,  # "sonnet" or "opus" based on routing
  prompt="Score this task result against the bound evaluation protocol.\n\nTask: {task_description}\nTask type: {taxonomy.task_type}\nSelected harness: {selected_harness}\nBound protocol: {bound_protocol}\nResult summary: {result_summary}\n\nRead protocols/{bound_protocol}/protocol.yaml for scoring dimensions.\nCheck for task_type_overrides matching task_type '{taxonomy.task_type}'.\nRead .meta-harness/sessions/{session_id}/evidence/ for collected evidence."
)
```

### Step 6: Record Evaluation and Update Weights (MANDATORY — do not skip)

On evaluator response:

**Execute immediately** after the evaluator returns. Write the eval JSON and update weights before responding to the user.

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

4. Clear the evaluation-pending flag: delete `.meta-harness/sessions/{session_id}/.eval-pending` via Bash to signal that evaluation is complete.

5. **Copy eval to evaluation-logs for evolution tracking (Fix 2):**
   ```
   mkdir -p .meta-harness/evaluation-logs/{selected_harness}/
   cp .meta-harness/sessions/{session_id}/eval-*.json .meta-harness/evaluation-logs/{selected_harness}/
   ```
   This accumulates evaluation history per harness, enabling the evolution-manager to analyze trends.

6. **Auto-trigger evolution manager every 5 evaluations (Fix 3):**
   After copying the eval, count files in `.meta-harness/evaluation-logs/{selected_harness}/`. If the count is a multiple of 5 (i.e., `count % 5 == 0` and `count >= 5`), spawn the evolution manager:
   ```
   Task(
     subagent_type="meta-harness:evolution-manager",
     prompt="Analyze evaluation history and propose harness improvements.\n\nTrigger: {selected_harness} has reached {count} evaluations.\n\nRead .meta-harness/evaluation-logs/{selected_harness}/ for evaluation history.\nRead harnesses/{selected_harness}/agent.md and skill.md for current harness content.\nRead .meta-harness/harness-pool.json for pool state.\n\nGenerate evolution proposals and write them to .meta-harness/evolution-proposals/."
   )
   ```
   The evolution-manager writes proposals to `.meta-harness/evolution-proposals/`. These proposals are applied automatically on the next session start by `session-start.sh` (which reads pending proposals, creates experimental harness copies, and registers them in the pool).

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

## Pre-Response Evaluation Gate

**Before generating ANY response to the user after receiving a task, verify:**

1. Did the router run? → If yes, check which path was taken:
   - `skip_routing: true` → verify lightweight eval JSON was written
   - Harness subagent ran → verify Steps 5-6 completed (eval JSON exists in `.meta-harness/sessions/{session_id}/`)
   - External skill handled the task → verify lightweight eval JSON was written with `harness: "external:{skill_name}"`
2. If NO eval JSON exists for this task, **STOP and run evaluation now** before responding.

This gate is the last line of defense against skipped evaluation. The pipeline is not complete until an eval record exists.

---

## Interaction with External Skills (OMC, superpowers)

When an OMC skill (`sciomc`, `ralph`, `autopilot`, `ultrawork`, etc.) or superpowers skill activates for the current task instead of the meta-harness pipeline, evaluation STILL applies:

1. Let the external skill complete its work
2. After it completes, write a lightweight eval JSON:
   ```
   {
     "task": "{task_description}",
     "timestamp": "{iso_timestamp}",
     "harness": "external:{skill_name}",
     "protocol": "none",
     "taxonomy": {},
     "scores": {},
     "overall_score": null,
     "quality_gate_passed": null,
     "external_skill": true
   }
   ```
3. Do NOT update harness weights (external results don't affect the pool)

This ensures observability — the evolution manager can detect when tasks are being handled outside the pipeline and whether those tasks would benefit from a harness.

---

## Key Design Constraints

- **You are the orchestrator** — this skill runs in the main conversation context. Do not spawn an "orchestrator" subagent.
- **Never execute harness work in the main context** — When the router selects a harness (`skip_routing=false`), you MUST spawn a Task() subagent. Do not read the harness `agent.md`/`skill.md` and follow those instructions yourself. The main context orchestrates; subagents execute. This separation is required for evaluation to work.
- **Subagents cannot spawn sub-subagents** — all fan-out (router, harness execution, evaluator, synthesizer) happens from the main context.
- **Evidence collection is automatic** — the `collect-evidence.sh` hook captures Bash tool output from harness subagents. You read it after subagent completion, you do not collect it manually.
- **Weights are in-memory during session** — maintain a simple dict of `{harness_name: adjusted_weight}` updates. Flush at session end via the Stop hook.
- **Harness content changes apply next session** — if the evolution-manager proposes changes to `agent.md`/`skill.md`/`contract.yaml`, write them to the experimental pool. They load on next SessionStart.

---

## Quick Reference: Harness Pool

Default stable pool (canonical trigger conditions in `agents/router.md`):
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
