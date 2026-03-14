# Ralph-Loop Skill

Persistent execution loop. Keep working on the task until all acceptance criteria pass, retrying with adapted strategies on each failure.

---

## Steps

1. **Understand task and prior chain context**
   - Read the task description carefully
   - If prior chain results exist (e.g., a plan from ralplan-consensus), read them fully
   - Identify acceptance criteria: tests passing, build clean, specific behavioral requirements
   - Note: do not re-plan if a plan was already provided by a prior chain step

2. **Explore the codebase**
   - Glob for source files and test files relevant to the task
   - Read key files to understand current structure and conventions
   - Identify the test runner command (check `package.json`, `Makefile`, `pytest.ini`, etc.)

3. **Implement**
   - Execute the implementation according to the plan (or the prior chain's plan)
   - Use Edit for modifying existing files, Write only for new files
   - Make targeted, minimal changes

4. **Verify**
   - Run tests and/or build — capture full output
   - Check all acceptance criteria
   - If all pass → proceed to step 6 (finalize)
   - If not → proceed to step 5 (iterate)

5. **Iterate on failure** (repeat up to 10 times total)
   - Diagnose: read the error output carefully
   - State clearly: "Iteration N failed because [reason]. Next attempt: [different approach]"
   - Change approach — do not repeat the same strategy that already failed
   - Return to step 3
   - After 10 iterations without success: escalate to user with full status

6. **Finalize**
   - Grep modified files for debug artifacts (`console.log`, `debugger`, `TODO`, `HACK`, `FIXME`) — remove any found
   - Run full test suite one final time — confirm all pass
   - Run build — confirm clean

7. **Report**
   - State total iteration count
   - Summarize what changed across iterations (what worked, what didn't)
   - Confirm final status: all criteria met OR escalating with reason
