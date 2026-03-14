# Ralplan-Consensus Skill

Create a structured implementation plan with self-review. Analyze the task, explore the codebase, propose an approach, identify risks, and challenge your own assumptions before handing the plan to downstream execution.

---

## Steps

1. **Analyze requirements**
   - Read the task description carefully
   - Identify: what is asked, what success looks like, what constraints exist
   - Note ambiguities or missing information
   - State the goal in one sentence

2. **Explore the codebase**
   - Glob for files relevant to the task (source, tests, config)
   - Read the most relevant files (limit to 5–7; prioritize by relevance)
   - Identify: where the change will be made, what depends on it, what patterns exist
   - Note surprising findings that affect the approach

3. **Create implementation plan**
   - Write numbered implementation steps (3–8 steps)
   - Each step must be: specific (names files/functions), ordered, and testable
   - Note for each step: what changes, where, and why

   **Adapt plan structure to task type:**
   - **Bugfix**: (1) reproduce the bug with a failing test, (2) isolate root cause, (3) implement minimal fix, (4) verify fix + regression test. Focus on: root cause analysis, minimal blast radius, regression prevention.
   - **Feature**: (1) define interface/API surface, (2) implement core logic, (3) add tests, (4) integrate with existing code, (5) update docs if needed. Focus on: API design, extensibility, test coverage.
   - **Refactor**: (1) write characterization tests for current behavior, (2) plan atomic steps (Mikado graph), (3) execute steps one at a time with test verification. Focus on: behavior preservation, atomic steps, rollback safety.
   - **Research**: (1) define metric + baseline, (2) plan experiment variants, (3) identify measurement methodology. Focus on: measurement rigor, hypothesis clarity, variable isolation.
   - **Migration**: (1) audit current usage, (2) plan migration steps with rollback commands, (3) identify breaking changes, (4) plan data migration if needed. Focus on: rollback safety, backwards compatibility, data integrity.

   If the task doesn't clearly fit one type, use the general structure (numbered steps with what/where/why).

4. **Consider alternatives**
   - Describe at least 1 alternative approach
   - Explain why the chosen approach is preferred

5. **Identify risks**
   - List at least 2 risks or unknowns
   - For each risk, suggest a mitigation step

6. **Self-review: challenge assumptions**
   - Play devil's advocate on your own plan
   - Challenge at least 2 assumptions
   - For each: either strengthen the plan or acknowledge the uncertainty
   - Final check: is the plan actionable without further clarification?

7. **Output structured plan**
   - Write the plan in structured markdown with sections:
     - Goal
     - Implementation Steps
     - Alternatives Considered
     - Risks and Mitigations
     - Assumptions Challenged
     - Key Files
   - This output becomes the `chain_context` for the next harness in the chain
