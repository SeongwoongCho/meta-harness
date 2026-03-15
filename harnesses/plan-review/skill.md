# Plan Review Skill

Thoroughly review an engineering plan before any code is written. Combines an engineering review (architecture, code quality, tests, performance) with mode selection for scope posture. Interactive: one issue per question, opinionated recommendations, required completion summary.

---

## Steps

### Phase 0: Scope Challenge

1. **Before reviewing anything, answer these questions:**
   - What existing code already partially or fully solves each sub-problem?
   - What is the minimum set of changes that achieves the stated goal?
   - Does the plan touch more than 8 files or introduce more than 2 new classes? Flag as a smell.

2. **Ask user to choose scope posture:**
   - A) **SCOPE REDUCTION** — propose a minimal version; review that
   - B) **HOLD SCOPE** — accept the plan's scope; make it bulletproof
   - C) **SCOPE EXPANSION** — push scope up; ask what would make this 10x better

   If user does not choose SCOPE REDUCTION: respect that decision fully. Do not re-argue for less scope in later sections.

---

### Phase 1: Four Review Sections

For each section: find issues, then for each issue call a separate question. Never batch.

Each issue question format:
- Describe problem concretely with file/line references
- Present 2-3 options (A, B, C); label with issue number + option letter (e.g., "1A", "1B")
- Lead with your recommendation: "We recommend B. Here's why..."
- Map reasoning to engineering preferences (DRY, explicit > clever, minimal diff)

**Stop after each section.** Move to next only after all issues in current section are resolved.

3. **Architecture review**
   - System design and component boundaries
   - Dependency graph and coupling
   - Data flow and bottlenecks
   - Security architecture (auth, data access, API boundaries)
   - One realistic production failure scenario per new codepath

4. **Code quality review**
   - DRY violations — be aggressive
   - Error handling and missing edge cases
   - Over-engineered or under-engineered areas
   - Naming, coupling, magic values

5. **Test review**
   - Diagram all new UX flows, codepaths, and branching logic
   - For each new item in the diagram: confirm a test exists or flag the gap
   - Acceptance: every new codepath has at least one test covering the happy path and one covering failure

6. **Performance review**
   - N+1 queries and database access patterns
   - Memory usage concerns
   - Caching opportunities
   - Slow or high-complexity code paths

---

### Phase 2: Required Outputs

7. **"NOT in scope" section**
   - List every item considered and explicitly deferred
   - One-line rationale per item

8. **"What already exists" section**
   - List existing code that partially solves sub-problems in this plan
   - Note whether the plan reuses or unnecessarily rebuilds each

9. **TODOS.md proposals**
   - Present each potential TODO as a separate question — never batch
   - For each: What, Why, Pros, Cons, Context, Depends on
   - Options: A) Add to TODOS.md, B) Skip, C) Build now in this PR

10. **Failure mode analysis**
    - For each new codepath: one realistic production failure (timeout, nil reference, race condition)
    - Flag as critical gap if: no test AND no error handling AND would be silent failure

11. **Completion summary**
    ```
    Step 0: Scope Challenge (user chose: ___)
    Architecture Review: ___ issues found
    Code Quality Review: ___ issues found
    Test Review: diagram produced, ___ gaps identified
    Performance Review: ___ issues found
    NOT in scope: written
    What already exists: written
    TODOS.md updates: ___ items proposed
    Failure modes: ___ critical gaps flagged
    ```

---

## Rules

- Read-only — never modify any files
- One issue = one question — never batch multiple issues
- Lead with your recommendation — be opinionated ("Do B. Here's why:")
- If a section has no issues: say so and move on
- After scope posture is agreed: commit to making that scope succeed
- Unresolved decisions: list at end as "Decisions left unresolved that may bite you later"
