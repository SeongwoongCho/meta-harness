---
description: "Manually evaluate the last task result or a specific change"
argument-hint: "[--last | --file=path]"
---

# adaptive-harness-eval

Manually trigger evaluation of a task result. Use this to re-evaluate the last completed task, evaluate a specific change, or run evaluation when auto-evaluation did not fire.

## Parsing Arguments

- `--last` — (default) Evaluate the most recent task result in this session
- `--file=path` — Evaluate a specific file or diff (e.g., `--file=src/auth.py`)
- No argument — same as `--last`

## Execution Steps

### Step 1: Identify What to Evaluate

**If `--last` or no argument:**

Find the most recent evaluation context in this session:
1. Check `.adaptive-harness/sessions/{session_id}/` for the latest evidence files
2. Read `.adaptive-harness/sessions/{session_id}/evidence/` — sort by timestamp, take most recent
3. If no evidence files exist, check if the last conversation turn produced code changes

If no evaluation context found:
```
No recent task result found to evaluate.

To evaluate a specific file: /adaptive-harness:eval --file=path/to/file
To run a task first: /adaptive-harness:run <task description>
```

**If `--file=path`:**

Read the specified file(s) to use as evaluation input. Accept glob patterns (e.g., `--file=src/**/*.py`).

### Step 2: Collect Evidence

Read all evidence files from `.adaptive-harness/sessions/{session_id}/evidence/` sorted by timestamp:

```
Read(".adaptive-harness/sessions/{session_id}/evidence/")
```

Also collect any git diff if available:
```bash
git diff --stat HEAD 2>/dev/null || echo "no git"
git diff HEAD 2>/dev/null | head -200
```

### Step 3: Spawn Evaluator Agent

```
Task(
  subagent_type="adaptive-harness:evaluator",
  prompt="Manually evaluate this task result.\n\nEvaluation target: {description of what's being evaluated}\n\nEvidence:\n{evidence_summary}\n\nGit diff (if available):\n{diff_output}"
)
```

### Step 4: Display Results

Show evaluation scores and write to state:

```
Manual evaluation complete.

Overall score: {score} ({PASS|FAIL})

Dimension scores:
  correctness:     {score}  — {brief_reasoning}
  completeness:    {score}  — {brief_reasoning}
  quality:         {score}  — {brief_reasoning}
  robustness:      {score}  — {brief_reasoning}
  clarity:         {score}  — {brief_reasoning}
  verifiability:   {score}  — {brief_reasoning}

Quality gate: {PASSED|FAILED — reason}

Suggestions:
  {improvement_suggestions}
```

Write result to `.adaptive-harness/sessions/{session_id}/eval-{timestamp}.json`.
