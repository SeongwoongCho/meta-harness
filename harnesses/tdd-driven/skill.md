# TDD-Driven Skill

Execute changes using strict red-green-refactor cycles. Every behavior is specified by a failing test before any production code is written.

---

## Steps

1. **Discover the test environment**
   - Glob for test files matching patterns like `*.test.*`, `*_test.*`, `*spec*`
   - Read 2–3 existing tests to learn the assertion library, test runner, and file naming conventions
   - Identify the test run command (check `package.json` scripts, `Makefile`, `pytest.ini`, `Cargo.toml`)

2. **Run the baseline test suite**
   - Execute the full test suite and confirm all existing tests pass
   - If any tests are failing before you start, stop and report — do not proceed on a broken baseline

3. **Decompose the task into behaviors**
   - List every distinct behavior the task requires (e.g., "returns 404 for missing resource", "increments counter on each call")
   - Order them from simplest to most complex
   - Confirm the list before proceeding

4. **RED — Write one failing test**
   - Write a single test for the first (simplest) behavior
   - Name it to communicate intent: `test_<subject>_<action>_<expected_outcome>`
   - Run the test suite and confirm the new test fails with an expected error (not a syntax error)
   - If it passes without implementation: the test is invalid — fix it

5. **GREEN — Write minimum production code**
   - Implement only enough production code to make the failing test pass
   - Do not add logic for behaviors not yet tested
   - Run the full test suite — confirm all tests pass, including previous ones
   - If tests still fail after 2 attempts: read the error message carefully, fix the root cause

6. **REFACTOR — Improve structure**
   - Review the new code: is there duplication? Poor naming? Mixed concerns?
   - Make one structural improvement at a time
   - Run the full test suite after each refactor step — never batch refactors
   - Stop when the code is clean and tests are green

7. **Repeat steps 4–6 for each remaining behavior**
   - Work through the behavior list one item at a time
   - Do not move to the next behavior until the current one is green and refactored
   - Maximum 10 red-green-refactor cycles per task

8. **Check coverage**
   - Run the coverage tool for modified modules
   - If coverage is below 80%: identify uncovered branches and write tests for them
   - Re-run coverage to confirm ≥ 80%

9. **Final verification**
   - Run the full test suite — all tests must pass
   - Run the build command — no compilation errors
   - Grep modified files for debug artifacts: `console.log`, `debugger`, `TODO`, `HACK`, `FIXME`
   - Remove any found artifacts

10. **Scope expansion verification**
    - Re-read the original task description
    - Extract all keywords representing distinct deliverables, features, or components
    - For each keyword, verify that a corresponding implementation exists:
      - If a deliverable is missing entirely: flag it as a scope gap
      - If a deliverable is stubbed but not fully implemented: flag it as incomplete
    - Common scope gaps to check for:
      - Infrastructure artifacts (Dockerfile, docker-compose) if the task mentions deployment
      - External service integrations that were mocked but never implemented for real
      - API endpoints that were designed but not exposed
      - Async/background processing if the task mentions long-running operations
      - Configuration management (.env, settings) if multiple environments are implied
    - If scope gaps are found:
      - Implement missing deliverables if they are within the task's requirements
      - Run tests after each addition to maintain green state
      - If implementation would exceed budget, document the gaps clearly in the report

11. **Report**
    - List all tests written (names and behaviors covered)
    - State final coverage percentage for modified modules
    - Note any behaviors deferred or not implemented (with reason)
    - **Scope verification results:** List each task keyword and whether it was implemented, stubbed, or missing
