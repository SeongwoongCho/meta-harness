# Parallel-Dispatch Skill

Decompose a task into 2–5 independent sub-tasks and emit a structured JSON so the orchestrator can fan them out in parallel worktrees. This harness only decomposes — it does NOT implement anything. Implementation is done by the fan-out agents in subsequent steps.

**Key distinction from ensemble**: Ensemble runs the *same* task through *different* harnesses for comparison. Parallel-dispatch runs *different* sub-tasks (potentially through the *same* harness) to exploit genuine independence.

---

## Steps

### Step 1: Analyze full scope

- Read every relevant file: source code, tests, configuration, interfaces, and the task description
- Map all modules, components, and concerns the task touches
- Identify which changes are genuinely independent (no shared state, no ordering constraint) vs. which must be sequenced
- If fewer than 2 independent sub-tasks can be found, emit a single-subtask result so the orchestrator falls back to single-harness execution

### Step 2: Decompose into 2–5 independent sub-tasks

For each sub-task, define:
- `id`: short slug (e.g., `"auth-layer"`, `"data-model"`, `"api-endpoints"`)
- `description`: one-paragraph description of what must be built or changed
- `scope_files`: list of files or directories this sub-task will modify (no overlap allowed between sub-tasks)
- `inputs`: interface contracts or data formats this sub-task depends on (from prior context or other sub-tasks)
- `outputs`: interface contracts this sub-task exposes to other sub-tasks or to integration
- `harness`: which harness should execute this sub-task (e.g., `"tdd-driven"`, `"careful-refactor"`)
- `estimated_complexity`: `low` | `medium` | `high`

Rules:
- Sub-task scope_files MUST NOT overlap. If two sub-tasks need the same file, merge them or extract a shared module
- Each sub-task must be completable in isolation — it cannot depend on uncommitted output of another sub-task
- Cap at 5 sub-tasks. If the task is larger, group related work or escalate to the user
- At least 2 sub-tasks must be present; if the task cannot be split into 2+ independent pieces, include a single sub-task and set `fallback_to_single: true`

### Step 3: Identify integration requirements

After all sub-tasks complete in their worktrees, they must be merged. Document:
- `integration_order`: recommended order in which sub-task branches should be merged (dependency-safe order)
- `conflict_zones`: files or interfaces likely to have merge conflicts — note how to resolve them
- `integration_test_plan`: what tests or checks confirm that the merged result is correct

### Step 4: Emit decomposition JSON

Output ONLY the following JSON block (no other text, no markdown wrapper outside the JSON):

```json
{
  "parallel_dispatch": true,
  "subtasks": [
    {
      "id": "subtask-slug",
      "description": "Full description of this sub-task",
      "scope_files": ["path/to/file.py", "path/to/module/"],
      "inputs": "What this sub-task assumes from prior context or sibling sub-tasks",
      "outputs": "What interface or contract this sub-task exposes",
      "harness": "tdd-driven",
      "estimated_complexity": "medium"
    }
  ],
  "integration": {
    "integration_order": ["subtask-slug-1", "subtask-slug-2"],
    "conflict_zones": ["path/to/shared.py"],
    "integration_test_plan": "Run pytest tests/integration/ after merging all branches"
  },
  "fallback_to_single": false,
  "decomposition_rationale": "Why this decomposition was chosen and what independence guarantee exists"
}
```

---

## Critical Rules

- **Emit only the decomposition JSON** — do not implement anything, do not write source files
- **Guarantee scope isolation** — if scope_files overlap, the fan-out will produce merge conflicts that break synthesis
- **Cap at 5 sub-tasks** — the orchestrator enforces this limit; decompositions with >5 sub-tasks are rejected
- **Always include integration guidance** — the orchestrator uses `integration_order` to sequence worktree merges
- **Set `fallback_to_single: true` if the task cannot be split** — this is not a failure; it signals the orchestrator to use single-harness execution instead
