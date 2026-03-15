# Simple-Executor Skill

Execute trivial, well-defined tasks directly. No planning, no TDD overhead. Read, change, verify, done.

---

## Steps

1. **Confirm triviality**
   - Re-read the task description
   - Confirm: single file or module scope, unambiguous outcome, easy to verify
   - If the task is not trivial, stop and request re-routing to `tdd-driven` or `ralplan-consensus`

2. **Locate files**
   - Use Glob or Grep to find all files that need to change
   - Read each file to understand context (do not read files that will not be changed)

3. **Make the change**
   - Apply the change using Edit (prefer) or Write (new files only)
   - Keep the diff minimal — no refactoring, no cleanup beyond the task scope

4. **Sanity check**
   - If a test file covers the changed code: run that one test file
   - If a linter is configured: run it on the changed file
   - If neither is available: visually verify the change looks correct

5. **Report**
   - State what changed and in which file(s)
   - State the sanity check result (pass / not applicable)
