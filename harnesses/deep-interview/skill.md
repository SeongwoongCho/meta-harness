# Deep-Interview Skill

Clarify ambiguous tasks through structured interviews before executing. Never write code against an unclear spec.

---

## Steps

1. **Analyze for ambiguity**
   - Read the task description carefully
   - Identify: unclear goals, missing constraints, undefined acceptance criteria, unknown stakeholders
   - List every ambiguity found

2. **Generate clarifying questions**
   - Write at most 5 questions, ordered by impact on the implementation
   - Frame questions to elicit concrete, actionable answers (prefer "What does success look like?" over "Is that right?")
   - Present all questions in one batch

3. **Wait for user response**
   - Do not proceed until the user answers
   - If answers introduce new ambiguities, ask one follow-up round (max 3 additional questions)

4. **Build the specification**
   - Write a structured spec containing:
     - **Goal**: one sentence describing the desired outcome
     - **Constraints**: non-negotiable limits (performance, compatibility, style)
     - **Acceptance criteria**: numbered list of verifiable pass/fail conditions
     - **Out of scope**: explicitly excluded items to prevent scope creep
   - Present the spec to the user and ask for confirmation

5. **Decompose into tasks**
   - Break the confirmed spec into ordered, independent implementation tasks
   - Each task should map to one or more acceptance criteria

6. **Execute tasks**
   - Implement each task in order
   - After each task, cross-check against the acceptance criteria it targets
   - Report progress as tasks complete

7. **Final verification**
   - Run through every acceptance criterion in the spec
   - For each criterion: state whether it is satisfied and cite the evidence
   - If any criterion is not met, fix it before reporting completion

8. **Completion summary**
   - List all acceptance criteria and their verification status
   - Note any criteria deferred with explicit user approval
