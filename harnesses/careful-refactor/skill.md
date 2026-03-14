# Careful Refactor Skill

Improve code structure without changing observable behavior. Use the Mikado method: one atomic step at a time, with test verification after every step.

---

## Steps

### Phase 0: Establish Safe Starting Point

1. **Run the full test suite**
   - All tests must pass before any refactoring begins
   - If tests are failing: STOP — do not refactor on a broken baseline. Report the failures.
   - Record: `Baseline: [N] tests passing`

2. **Confirm clean git state**
   - Run `git status` to check if working tree is clean
   - If uncommitted changes exist: note them — they are not part of this refactor

---

### Phase 1: Characterize

3. **Understand the code to be refactored**
   - Read the target file(s) completely
   - Identify: inputs, outputs, side effects, and invariants that must be preserved
   - Note any implicit contracts (error conditions, ordering dependencies, global state mutations)

4. **Map all call sites**
   - Grep for every function/class/variable being renamed or moved
   - List all files that will need updating if the interface changes

5. **Assess test coverage**
   - Identify which behaviors of the target code are covered by existing tests
   - For any uncovered behaviors: write characterization tests
     - Characterization tests document current behavior — they capture reality, not spec
     - Run them to confirm they pass (they must pass on the current code)

---

### Phase 2: Plan the Mikado Graph

6. **Define the target structure**
   - Describe what the code should look like after refactoring
   - Keep the target realistic — this is one refactoring session, not a full rewrite

7. **Break into atomic steps**
   - Each step must: be independently reversible, leave the codebase passing all tests, and change only one structural concern
   - Order from least risky to most risky
   - Example steps: extract function, rename variable, move function to module, inline constant, split class

8. **Document the plan and rollback**
   - Write out each step with its success criterion and its rollback command
   - Write the complete rollback sequence (reverse order of all steps)

---

### Phase 3: Execute (one step at a time)

9. **For each step in the plan:**

   a. Announce: "Applying step [N]: [description]"

   b. Apply the change using Edit (one file at a time)

   c. Run the full test suite immediately

   d. If all tests pass:
      - Record: "Step [N] complete. [N] tests passing."
      - Proceed to the next step

   e. If any test fails:
      - Do NOT proceed
      - Revert the change: `git checkout -- [file]` or manually restore
      - Run the test suite again to confirm baseline is restored
      - Re-examine: is the characterization complete? Was a dependency missed?
      - Either adjust the plan and retry, or stop and report

10. **Run the full test suite every 3 steps** — even if nothing seems wrong

---

### Phase 4: Verify Behavior Preservation

11. **Run the full test suite** — all original tests must pass

12. **Run characterization tests** — all must pass (current behavior unchanged)

13. **Review the diff**
    - Run `git diff --stat` to review the scope
    - Confirm: only structural changes, no logic changes, no new behaviors added

---

### Phase 5: Cleanup

14. **Remove redundant characterization tests**
    - If a characterization test duplicates an existing test, remove it
    - Keep the better-named, better-structured one

15. **Remove temporary refactoring scaffolding**
    - Any helper code introduced only to facilitate the refactor should be removed

16. **Final build check**
    - Run the build — no compilation errors

17. **Cleanup check**
    - Grep modified files for: `console.log`, `debugger`, `TODO`, `HACK`

18. **Report**
    - Files changed: [N]
    - Tests: [N] passing
    - Structure improved: [one sentence per major improvement]
    - Deferred: any planned steps that were not executed (with reason)
