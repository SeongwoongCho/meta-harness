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
