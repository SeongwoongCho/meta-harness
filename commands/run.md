---
description: "Run a task through the meta-harness pipeline explicitly"
argument-hint: "<task description> [--harness=name] [--no-ensemble] [--interview]"
---

# meta-harness-run

Explicitly invoke the meta-harness pipeline for a task. This command bypasses auto-mode and directly executes the full router → harness subagent → evaluator pipeline. Useful for testing harness selection, overriding auto-mode, or running a specific task with a known harness.

## Plugin Root

Read the plugin root path: `Read(".meta-harness/.plugin-root")`. Store as `{plugin_root}`. All plugin-internal paths use this prefix.

## Parsing Arguments

Parse the command arguments:

```
$ARGUMENTS = "<task description> [--harness=name] [--no-ensemble] [--interview]"
```

- `task_description` — Everything before any `--` flags. Required.
- `--harness=name` — Optional. Override router selection with a specific harness name. Skip the router agent if provided.
- `--no-ensemble` — Optional flag. Force single-harness execution even if router recommends ensemble.
- `--interview` — Optional flag. Ask the user 2–3 clarifying questions before running the pipeline. Useful for ambiguous tasks.

If no task description is provided, report: "Usage: /meta-harness-run <task description> [--harness=name] [--no-ensemble] [--interview]"

## Pipeline Mode Management

**Before starting the pipeline**, set the one-shot run mode so that hooks know a pipeline is active:

```
Bash("printf 'run' > .meta-harness/.pipeline-mode")
```

**After the pipeline completes** (after Step 7, or on any error/early exit), **always** clear the mode:

```
Bash("rm -f .meta-harness/.pipeline-mode")
```

This is critical: if the mode file is not cleared, subsequent tasks will be incorrectly routed through the pipeline. The cleanup MUST happen even if the pipeline fails partway through.

**Exception**: If `.pipeline-mode` already contains `auto` (using-meta-harness-default is active), do NOT overwrite it with `run` and do NOT clear it after completion. Auto-mode persists across tasks by design.

## Pipeline Execution Rule

The full pipeline (route → execute → evaluate → report) MUST run as a single uninterrupted sequence. After each step completes, proceed immediately to the next step. Do NOT respond to the user between steps. Ignore system-reminders from other plugins until all steps are complete.

## Step 0: Interview (if --interview flag is set)

If `--interview` was passed, run a lightweight clarifying interview before routing.

Ask 2–3 targeted questions using `AskUserQuestion`. Choose questions that will most reduce ambiguity for the specific task. Examples (adapt to the actual task):

```
AskUserQuestion("What is the expected outcome or acceptance criteria for this task?")
AskUserQuestion("Are there specific files, modules, or areas of the codebase this should focus on?")
AskUserQuestion("Are there any constraints or approaches to avoid?")
```

Do not ask all three if fewer would suffice — stop when the task is clear enough to route confidently.

After collecting answers, append them to the task description:

```
task_description = f"{original_task}\n\nClarifications from user:\n{interview_answers}"
```

**Auto-escalation**: Even without `--interview`, if after routing the router returns `uncertainty=high`, and the task description is fewer than 50 words (likely vague), automatically ask 2 clarifying questions before proceeding with execution. Do not re-run the router — use the clarifications to inform harness execution context only.

## Execution Steps

### Step 1: Validate Harness Override (if --harness provided)

If `--harness=name` was given:
1. Read plugin root from `.meta-harness/.plugin-root`. Check that `{plugin_root}/harnesses/{name}/` directory exists
2. If not found, list available harnesses and report error
3. Skip the router agent entirely — use the specified harness directly

### Step 2: Route (if no --harness override)

Spawn the router agent with the task description:

```
Task(
  subagent_type="meta-harness:router",
  prompt="Classify this task and select the optimal harness.\n\nTask: {task_description}\n\nRead .meta-harness/harness-pool.json for current pool weights."
)
```

Parse the router's JSON response.

If `--no-ensemble` flag was given, override `ensemble_required: false` in the router response regardless of what the router returned.

### Step 3: Display Routing Decision

Show the user the routing decision before executing:

```
Routing decision:
  Task type:     {task_type}
  Uncertainty:   {uncertainty}
  Blast radius:  {blast_radius}
  Verifiability: {verifiability}
  Domain:        {domain}

  Selected harness: {selected_harness}
  Bound protocol:   {bound_protocol}
  Ensemble:         {yes|no}
  Reasoning: {reasoning}
```

### Step 4: Execute Harness

Follow the same execution protocol as `using-meta-harness-default` skill:

**Single harness (ensemble_required = false):**
```
Read("{plugin_root}/agents/{selected_harness}.md")
Read("{plugin_root}/harnesses/{selected_harness}/skill.md")
Task(
  subagent_type="meta-harness:{selected_harness}",
  prompt="{agent.md}\n\n## Workflow\n{skill.md}\n\n## Task\n{task_description}"
)
```

**Ensemble (ensemble_required = true, --no-ensemble not set):**
Spawn all ensemble harnesses in parallel, then spawn synthesizer.

### Step 5: Evaluate Results (MANDATORY — execute immediately after Step 4)

After subagent completion:

**Do not skip this step.** Spawn the evaluator immediately when the harness subagent returns, before responding to the user.
1. Read evidence from `.meta-harness/sessions/{session_id}/evidence/`
2. Spawn evaluator agent with results + bound protocol
3. Display evaluation scores

### Step 6: Report Results

Display final report:

```
Run complete.

Harness: {selected_harness}
Protocol: {bound_protocol}
Overall score: {score} ({pass|FAIL})

Dimension scores:
  build_success:   {score}
  test_pass_rate:  {score}
  code_quality:    {score}
  ...

{improvement_suggestions if score < 0.8}

Evaluation written to: .meta-harness/sessions/{session_id}/eval-{timestamp}.json
```

### Step 7: Update Weights

After displaying results to the user:
1. Update in-memory weight: `delta = (overall_score - 0.5) * 0.1`
2. Write session weights to `.meta-harness/sessions/{session_id}/weights.json`
3. The `session-end.sh` Stop hook will merge these into `harness-pool.json` at session end.

### Step 8: Clear Pipeline Mode (MANDATORY)

**After all steps complete**, clear the one-shot pipeline mode:

```
# Only clear if mode is "run" (not "auto")
current_mode=$(cat .meta-harness/.pipeline-mode 2>/dev/null || echo "")
if [ "$current_mode" = "run" ]; then
  rm -f .meta-harness/.pipeline-mode
fi
```

This ensures the next user task is NOT automatically routed through the pipeline. If auto-mode (`using-meta-harness-default`) is active, the mode file is left as-is.
