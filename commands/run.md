---
description: "Run a task through the meta-harness pipeline explicitly"
argument-hint: "<task description> [--harness=name] [--no-ensemble] [--interview]"
---

# meta-harness-run

Explicitly invoke the meta-harness pipeline for a task. This command bypasses auto-mode and directly executes the full router → harness subagent → evaluator pipeline. Useful for testing harness selection, overriding auto-mode, or running a specific task with a known harness.

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
1. Check that `harnesses/{name}/` directory exists
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
Read("harnesses/{selected_harness}/agent.md")
Read("harnesses/{selected_harness}/skill.md")
Task(
  subagent_type="meta-harness:{selected_harness}",
  prompt="{agent.md}\n\n## Workflow\n{skill.md}\n\n## Task\n{task_description}"
)
```

**Ensemble (ensemble_required = true, --no-ensemble not set):**
Spawn all ensemble harnesses in parallel, then spawn synthesizer.

### Step 5: Evaluate Results

After subagent completion:
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
