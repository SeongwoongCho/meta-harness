# Synthesizer Skill

Merge two or more independent codebases (from ensemble worktrees) into a single, coherent, working project in the main workspace. This is not a summary — you physically read, compare, and write files.

---

## Inputs

You receive:
- `main_workspace`: the original project directory (target for merged output)
- `worktrees`: list of `{path, branch, harness, result_summary}` — each is an independent implementation
- `task_description`: what was originally asked
- `planning_context`: shared plan from ralplan-consensus (if chain ensemble)

---

## Steps

### Phase 1: Inventory (read-only, no writes yet)

1. **List all files in each worktree**
   - For each worktree, run: `find {worktree_path} -type f -not -path '*/.git/*' -not -path '*__pycache__*' -not -path '*.pyc'`
   - Record the full file list per worktree
   - Identify the project root within each worktree (may be the worktree root or a subdirectory)

2. **Categorize files into layers**
   Assign every file to exactly one layer:

   | Layer | Examples | Priority source |
   |-------|---------|-----------------|
   | **Infrastructure** | Dockerfile, docker-compose.yml, .env.example, Makefile | Prefer the worktree with more complete infra |
   | **Configuration** | pyproject.toml, requirements.txt, package.json, tsconfig.json | Merge dependencies from both |
   | **Source code** | app/*.py, src/*.ts, lib/*.go | Compare file-by-file |
   | **Tests** | tests/*.py, *_test.go, *.spec.ts | Prefer the worktree with more tests AND higher coverage |
   | **Dashboards/Provisioning** | grafana/*.json, prometheus.yml, alerting rules | Prefer the worktree that has them |
   | **Documentation** | README.md, docs/*.md, .env.example | Merge if both exist, otherwise take whichever has it |

3. **Build a comparison matrix**
   For each file that exists in both worktrees:
   - Read both versions
   - Note: which is longer? which has better error handling? which has tests covering it?
   - Assign a winner (A, B, or MERGE) per file

   For files that exist in only one worktree:
   - Mark as UNIQUE-A or UNIQUE-B
   - These are automatically included (they represent that worktree's unique contribution)

### Phase 2: Merge Plan

4. **Create an explicit merge plan before writing anything**
   Output a table:

   ```
   | File | Source | Reason |
   |------|--------|--------|
   | Dockerfile | Worktree A | Only A has it |
   | docker-compose.yml | Worktree A | Only A has it |
   | app/main.py | Worktree A | Has lifespan mgmt, structured logging |
   | app/services/analyzer.py | MERGE | A has async worker, B has better error handling |
   | tests/test_webhook.py | Worktree B | 14 tests vs 6, covers edge cases |
   | tests/test_analysis.py | Worktree B | Higher coverage (100% vs 82%) |
   | pyproject.toml | MERGE | Union of dependencies from both |
   | grafana/dashboard.json | Worktree A | Only A has dashboards |
   ```

   Rules for the merge plan:
   - Infrastructure files: take from whichever worktree has them; if both, prefer the more complete one
   - Source files: compare quality (error handling, async patterns, security); pick the better version
   - Test files: ALWAYS prefer the worktree with more tests and higher coverage
   - Config files: merge dependencies (union, not intersection); resolve version conflicts by taking the higher version
   - If a source file from worktree B is chosen but its imports reference a module that only exists in worktree A, flag this as a dependency conflict and resolve it

### Phase 3: Execute Merge

5. **Write infrastructure files first**
   - Copy Dockerfile, docker-compose.yml, Grafana configs, .env.example from the winning worktree
   - These are copied verbatim — do not modify them

6. **Write configuration files**
   - For pyproject.toml / requirements.txt / package.json:
     - Parse dependencies from both worktrees
     - Create a merged dependency list (union)
     - If the same package has different version constraints, use the broader range or the higher minimum
   - Write the merged config to main workspace

7. **Write source code files**
   - For files where one worktree wins outright: copy verbatim from the winner
   - For files marked MERGE: read both versions, construct a merged version that takes the best parts of each
     - Prefer the version with: better error handling, async patterns, input validation, logging
     - Ensure imports are consistent with the merged codebase (no dangling imports)
   - For UNIQUE files: copy from whichever worktree has them

8. **Write test files**
   - Copy test files from the worktree with better test coverage
   - If worktree A has tests that worktree B doesn't (e.g., test_infrastructure.py), include those too
   - Ensure test imports match the merged source code (fix import paths if needed)

### Phase 4: Reconcile

9. **Fix import conflicts**
   - Grep all Python files for import statements
   - For each import, verify the target module exists in the merged codebase
   - Fix any broken imports (wrong module name, missing file, different package structure)
   - Common issues:
     - Worktree A uses `from app.worker import ...` but merged code doesn't have worker.py → add it from A
     - Worktree B imports `from services.analysis import ...` but merged structure is `app.services.analysis` → fix path

10. **Resolve architectural conflicts**
    - If both worktrees define the same class/function differently:
      - Compare: which has more features? which has better error handling?
      - Take the more complete version, then backport specific improvements from the other
    - If worktrees use different frameworks for the same purpose (e.g., Celery vs BackgroundTasks):
      - Prefer the more production-ready choice (Celery > BackgroundTasks for high-volume)
      - Ensure the choice is consistent throughout the codebase (no mixed patterns)
    - If the conflict cannot be resolved without user input, document it clearly and proceed with the safer choice

### Phase 5: Verify

11. **Install dependencies**
    ```
    cd {main_workspace}
    pip install -e ".[dev]" 2>&1 || pip install -e ".[test]" 2>&1 || pip install -r requirements.txt 2>&1
    ```
    Fix any dependency errors before proceeding.

12. **Run the test suite**
    ```
    cd {main_workspace}
    python -m pytest tests/ -x -q 2>&1
    ```
    - If tests pass: proceed to step 13
    - If tests fail: read the error, fix the root cause (usually import mismatch or missing module), re-run
    - Maximum 3 fix-and-retry cycles. If still failing after 3 attempts, document the failures and proceed

13. **Run coverage check** (if pytest-cov available)
    ```
    python -m pytest tests/ --cov=app --cov-report=term-missing -q 2>&1
    ```
    Record coverage percentage for the report.

14. **Verify infrastructure** (if Dockerfile/docker-compose exists)
    - Check that Dockerfile references the correct entry point and dependencies
    - Check that docker-compose.yml services reference correct ports and env vars
    - Do NOT run docker-compose (may not be available) — just verify file consistency

### Phase 6: Report

15. **Output the synthesis report**
    Include in your output:

    ```
    ## Synthesis Report

    ### Merge Plan Executed
    [the table from step 4]

    ### Files Written
    - Total files: N
    - From worktree A: N (list key files)
    - From worktree B: N (list key files)
    - Merged: N (list files with explanation)

    ### Test Results
    - Tests: N passed / N failed
    - Coverage: X%

    ### Conflicts Resolved
    - [list any architectural conflicts and how they were resolved]

    ### Provenance
    - Infrastructure: from {harness_name} (worktree A)
    - Source code: mixed (details in merge plan)
    - Tests: primarily from {harness_name} (worktree B)
    - Configuration: merged from both

    ### Quality Assessment
    - Correctness: [brief note]
    - Completeness: [brief note — all task requirements addressed?]
    - Test coverage: X%
    ```

---

## Critical Rules

- **NEVER skip Phase 1 (Inventory)**. You must read actual files from both worktrees. Summaries lie — files don't.
- **NEVER output only a JSON report**. The synthesizer's job is to produce a WORKING CODEBASE in the main workspace. JSON reports are supplementary.
- **ALWAYS include unique files from both worktrees**. If worktree A has a Dockerfile and B doesn't, the Dockerfile goes into the merge. Period.
- **ALWAYS run tests after merging**. An untested merge is a failed merge.
- **PREFER tests from the worktree with higher coverage**. Tests are the most valuable artifact — never discard a higher-coverage test suite.
- **PREFER infrastructure from the worktree that has it**. Dockerfile, docker-compose, Grafana configs are high-effort artifacts that should never be silently dropped.
- **FIX imports after merging**. The #1 cause of merge failures is import path mismatches between worktrees. Always verify imports.
