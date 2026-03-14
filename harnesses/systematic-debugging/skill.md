# Systematic Debugging Skill

Diagnose and fix bugs through four strict phases. Never guess — every hypothesis is tested with evidence before a fix is applied.

---

## Steps

### Phase 1: Reproduce

1. **Parse the bug report**
   - Extract: what is the expected behavior, what is the actual behavior, any error messages or stack traces
   - Identify the entry point (API endpoint, function, CLI command, UI interaction) that triggers the bug

2. **Locate relevant code**
   - Grep for the error message text or the function/class mentioned in the stack trace
   - Glob to map the module structure around the suspected area
   - Read the primary file(s) to understand the code path

3. **Build a minimal reproduction case**
   - Use an existing failing test if one exists
   - Otherwise: write a minimal test or Bash command that triggers the bug
   - The reproduction case must be automated — not "open the browser and click"

4. **Confirm reproducibility**
   - Run the reproduction case and observe the bug
   - Record: `REPRODUCE: [command] → [observed error/output]`
   - If the bug does not reproduce: stop and report — do not guess at a fix

---

### Phase 2: Isolate

5. **Form Hypothesis 1**
   - State the hypothesis specifically: "I believe the bug is in `[function]` at `[file:line]` because `[reasoning]`"
   - Read the relevant code path from trigger to failure

6. **Test Hypothesis 1**
   - Write a focused test or add targeted logging to confirm or refute the hypothesis
   - Run it and observe the result

7. **Evaluate Hypothesis 1**
   - If confirmed: record `ISOLATE: Root cause is [description]. Evidence: [output]. Location: [file:line]`
   - If refuted: record the refutation and form Hypothesis 2

8. **Repeat for Hypothesis 2 and Hypothesis 3 if needed**
   - Each hypothesis must be distinct from the previous (do not re-test the same thing)
   - Maximum 3 hypotheses — if all three are refuted, escalate to user with full findings

---

### Phase 3: Fix

9. **Design the minimal fix**
   - Change only the lines that implement the incorrect behavior
   - If the fix requires more than 10 lines of change: re-examine whether root cause is truly identified

10. **Apply the fix**
    - Use Edit to modify only the lines that are incorrect
    - Do not introduce new functions, abstractions, or dependencies as part of a bug fix

11. **Run the reproduction case**
    - Confirm the bug no longer occurs
    - Record: `FIX: [description of change]. [file:line changed]`

12. **Run the full test suite**
    - All previously passing tests must still pass
    - If new failures appear: read them carefully — they may indicate the fix is incomplete or wrong

---

### Phase 4: Verify

13. **Write a regression test**
    - Create a test named to describe the bug it prevents (e.g., `test_login_does_not_crash_on_empty_password`)
    - The test must exercise the exact scenario that was broken
    - Confirm it passes with the fix in place

14. **Run the full test suite one final time**
    - All tests must pass
    - Zero regressions from the fix

15. **Review for side effects**
    - Re-read the modified code: could this change affect any other behavior?
    - If yes: write an additional test to confirm that behavior is preserved

16. **Build verification**
    - Run the build — no compilation errors

17. **Cleanup check**
    - Grep modified files for: `console.log`, `debugger`, `TODO`, `HACK`
    - Remove all debug artifacts

18. **Report**
    - Root cause: one sentence describing the bug's cause
    - Fix: one sentence describing the change made
    - Regression test: name of the test written
    - Confidence: High / Medium (based on how well-isolated the root cause was)
