---
description: "Run a task through the adaptive-harness pipeline explicitly"
argument-hint: "<task description> [--harness=name] [--no-ensemble] [--skip-interview]"
---

# adaptive-harness-run

## MANDATORY EXECUTION ORDER — READ THIS FIRST

**You are a pipeline orchestrator, not a task executor.** The task description in `$ARGUMENTS` is an opaque payload — do NOT read it, analyze it, or act on it yourself. Your ONLY job is to pass it through the pipeline steps below.

**Your first tool call MUST be one of:**
- `Read(".adaptive-harness/.plugin-root")` (to get plugin root), OR
- `Bash("printf 'run' > .adaptive-harness/.pipeline-mode")` (to set pipeline mode)

If your first tool call is anything else (Glob, Grep, reading source files, exploring the codebase), you are violating the protocol. STOP and re-read this section.

**Pipeline sequence — execute all steps in order, no exceptions:**
1. Parse arguments (extract task_description and flags from `$ARGUMENTS`)
2. Set pipeline mode → `Bash("printf 'run' > .adaptive-harness/.pipeline-mode")`
3. (Unless --skip-interview) Ask 2-3 clarifying questions
4. Spawn router agent → `Agent(subagent_type="adaptive-harness:router", ...)`
5. Display routing decision to user
6. Spawn harness subagent → `Agent(subagent_type="adaptive-harness:{harness}", ...)`
7. Spawn evaluator agent → `Agent(subagent_type="adaptive-harness:evaluator", ...)`
8. Display results, update weights
9. Clear pipeline mode → `Bash("rm -f .adaptive-harness/.pipeline-mode")`

**Do NOT respond to the user between steps.** Do NOT explore the codebase yourself. Do NOT execute the task yourself. The full pipeline runs as a single uninterrupted sequence.

---

## Plugin Root

Read the plugin root path: `Read(".adaptive-harness/.plugin-root")`. Store as `{plugin_root}`. All plugin-internal paths use this prefix.

## Parsing Arguments

Parse the command arguments:

```
$ARGUMENTS = "<task description> [--harness=name] [--no-ensemble] [--skip-interview]"
```

- `task_description` — Everything before any `--` flags. Required. Treat as opaque text to pass to the router.
- `--harness=name` — Optional. Override router selection with a specific harness name. Skip the router agent if provided.
- `--no-ensemble` — Optional flag. Force single-harness execution even if router recommends ensemble.
- `--skip-interview` — Optional flag. Skip the default clarifying interview and let the system decide autonomously. By default (without this flag), 2-3 clarifying questions are asked before routing.

If no task description is provided, report: "Usage: /adaptive-harness:run <task description> [--harness=name] [--no-ensemble] [--skip-interview]"

## Pipeline Mode Management

**Before starting the pipeline**, set the one-shot run mode so that hooks know a pipeline is active:

```
Bash("printf 'run' > .adaptive-harness/.pipeline-mode")
```

**After the pipeline completes** (after Step 8, or on any error/early exit), **always** clear the mode:

```
Bash("rm -f .adaptive-harness/.pipeline-mode")
```

**Exception**: If `.pipeline-mode` already contains `auto` (using-adaptive-harness is active), do NOT overwrite it with `run` and do NOT clear it after completion. Auto-mode persists across tasks by design.

## Step 0: Interview (default — skipped if --skip-interview flag is set)

By default, run a lightweight clarifying interview before routing. If `--skip-interview` was passed, skip this step and let the system decide autonomously.

Ask 2–3 targeted questions using `AskUserQuestion`. Choose questions that will most reduce ambiguity for the specific task.

After collecting answers, append them to the task description:

```
task_description = f"{original_task}\n\nClarifications from user:\n{interview_answers}"
```

**Auto-escalation**: Even when `--skip-interview` is set, if after routing the router returns `uncertainty=high`, and the task description is fewer than 50 words, automatically ask 2 clarifying questions before proceeding with execution.

## Step 1: Validate Harness Override (if --harness provided)

If `--harness=name` was given:
1. Read plugin root from `.adaptive-harness/.plugin-root`. Check that `{plugin_root}/harnesses/{name}/` directory exists
2. If not found, list available harnesses and report error
3. Skip the router agent entirely — use the specified harness directly, jump to Step 4

## Step 2: Route (if no --harness override)

**Spawn the router agent NOW.** This is the critical step — do not skip it.

```
Agent(
  subagent_type="adaptive-harness:router",
  description="Route task to harness",
  prompt="Classify this task and select the optimal harness.\n\nTask: {task_description}\n\nRead .adaptive-harness/harness-pool.json for current pool weights."
)
```

Parse the router's JSON response.

If `--no-ensemble` flag was given, override `ensemble_required: false` in the router response regardless of what the router returned.

## Step 3: Display Routing Decision

Show the user the routing decision before executing:

```
Routing decision:
  Task type:     {task_type}
  Uncertainty:   {uncertainty}
  Blast radius:  {blast_radius}
  Verifiability: {verifiability}
  Domain:        {domain}

  Selected harness: {selected_harness}
  Ensemble:         {yes|no}
  Reasoning: {reasoning}
```

## Step 4: Execute Harness

**MANDATORY: Spawn a subagent.** Do NOT read the harness instructions and follow them yourself. You MUST use the Agent tool. The orchestrator orchestrates; subagents execute.

**Single harness (ensemble_required = false):**
```
Read("{plugin_root}/agents/{selected_harness}.md")
Read("{plugin_root}/harnesses/{selected_harness}/skill.md")
Agent(
  subagent_type="adaptive-harness:{selected_harness}",
  description="Execute {selected_harness} harness",
  prompt="{agent.md}\n\n## Workflow\n{skill.md}\n\n## Task\n{task_description}"
)
```

If the router returned `harness_chain` with more than 1 entry, execute them sequentially, passing accumulated context from each step to the next.

**Ensemble (ensemble_required = true, --no-ensemble not set):**
Spawn all ensemble harnesses in parallel, then spawn synthesizer.

## Step 5: Evaluate Results (MANDATORY — execute immediately after Step 4)

**Do not skip this step.** Spawn the evaluator immediately when the harness subagent returns, before responding to the user.

1. Read session ID from `.adaptive-harness/.current-session-id`
2. Read evidence from `.adaptive-harness/sessions/{session_id}/evidence/`
3. Spawn evaluator agent:

```
Agent(
  subagent_type="adaptive-harness:evaluator",
  description="Evaluate harness results",
  prompt="Score this task result.\n\nTask: {task_description}\nSelected harness: {selected_harness}\nResult summary: {result_summary}\n\nRead .adaptive-harness/sessions/{session_id}/evidence/ for collected evidence."
)
```

## Step 6: Report Results

Display final report:

```
Run complete.

Harness: {selected_harness}
Overall score: {score} ({pass|FAIL})

Dimension scores:
  correctness:     {score}
  completeness:    {score}
  quality:         {score}
  robustness:      {score}
  clarity:         {score}
  verifiability:   {score}

{improvement_suggestions if score < 0.8}

Evaluation written to: .adaptive-harness/sessions/{session_id}/eval-{timestamp}.json
```

## Step 7: Update Weights

After displaying results to the user:
1. Update in-memory weight: `delta = (overall_score - 0.5) * 0.1`
2. Write session weights to `.adaptive-harness/sessions/{session_id}/weights.json`
3. The `session-end.sh` Stop hook will merge these into `harness-pool.json` at session end.

## Step 8: Clear Pipeline Mode (MANDATORY)

**After all steps complete**, clear the one-shot pipeline mode:

```
current_mode=$(cat .adaptive-harness/.pipeline-mode 2>/dev/null || echo "")
if [ "$current_mode" = "run" ]; then
  rm -f .adaptive-harness/.pipeline-mode
fi
```

This ensures the next user task is NOT automatically routed through the pipeline.
