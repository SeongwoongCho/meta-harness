# Rapid Prototype Skill

Build the minimum viable implementation of a feature as fast as possible. Cut scope aggressively. Prove the concept works. Document everything deferred.

---

## Steps

1. **Scope triage (2 minutes max)**
   - Read the task description
   - List every item in the task. Tag each: `[CORE]`, `[NICE]`, `[SKIP]`
     - CORE: Without this, the feature does not exist
     - NICE: Useful but deferrable (full error handling, edge cases, tests beyond smoke)
     - SKIP: Out of scope for MVP (optimization, i18n, theming, pagination)
   - Announce the decision: "I will implement [CORE items]. I defer [NICE items]. I skip [SKIP items]."

2. **Map the project structure**
   - Glob for relevant source files, config files, and existing feature directories
   - Identify where the new code will live (follow existing file placement patterns)
   - Read one or two similar existing features to learn naming and structural conventions

3. **Implement CORE item 1**
   - Read the immediate context files needed for this item
   - Write the implementation using existing patterns — do not invent new abstractions
   - Use Edit for existing files, Write for new files
   - Keep the implementation minimal: happy path only

4. **Sanity-check CORE item 1**
   - Run a quick Bash command to confirm the code does not crash immediately
   - Fix any immediate syntax/import errors before moving on

5. **Implement CORE item 2 (and subsequent CORE items)**
   - Repeat steps 3–4 for each CORE item
   - After every 2 CORE items: estimate remaining budget — stop if at 80%

6. **End-to-end smoke test**
   - Run the simplest possible test of the complete feature:
     - Use an existing test covering the happy path if one exists
     - Write one new test covering the primary use case if needed
     - Or run a Bash command that exercises the feature end-to-end
   - Confirm: feature works for the primary use case
   - If smoke test fails: fix only the immediate crash/error — do not expand scope

7. **Cleanup**
   - Grep modified files for: `console.log`, `debugger`, `TODO`, `HACK`
   - Remove obvious debug artifacts but keep intentional `// TODO: [deferred item]` markers

8. **Handoff report**
   - **Implemented (CORE):** List what was built and confirmed working
   - **Deferred (NICE):** List each item with a rough effort estimate
   - **Skipped (SKIP):** List each item with a one-line rationale
   - **Known limitations:** Edge cases not handled, error states not covered
   - **How to run:** The exact command to exercise the feature
   - **Assumptions made:** Any ambiguous requirements that were resolved by choosing an interpretation
