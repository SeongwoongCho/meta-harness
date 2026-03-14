# Migration Safe Skill

Execute migrations — schema changes, dependency upgrades, API version changes, large-scale restructuring — with complete audit trails and verified rollback plans.

---

## Steps

### Phase 1: Audit

1. **Parse the migration task**
   - Identify: what is being migrated, what is the source state, what is the target state
   - Categorize the migration type: schema, dependency, API, code restructuring

2. **Map current usage**
   - Glob to find all files in the migration scope
   - Grep to find every usage of the thing being migrated (old table name, old package import, old API call)
   - Count: affected files, call sites, modules

3. **Identify breaking changes**
   - For each usage found: will it break immediately (compile/runtime error) or silently (behavior change)?
   - List: breaking changes, behavioral changes, interface changes

4. **Identify external dependencies**
   - Are there external consumers (published APIs, other repos) that cannot be updated in this migration?
   - If yes: document them explicitly — they may block the migration or require a compatibility layer

5. **Assess data risks** (for data migrations)
   - Is the transformation reversible or lossy?
   - How many records/rows are affected?
   - Is a backup available or can one be created?

6. **Record the audit**
   - `AUDIT: [migration type]. Breaking changes: [list]. Affected files: [N]. Call sites: [N]. Risks: [list].`

---

### Phase 2: Migration Plan

7. **Define atomic steps**
   - Break the migration into independently reversible steps
   - Each step: leaves the system working, has a success check command, has a rollback command
   - Order from least risky to most risky

8. **Document rollback plan**
   - The complete reverse sequence with exact commands for each step
   - Note: any steps that are irreversible (must be explicitly acknowledged)

---

### Phase 3: Execute

9. **For each migration step:**

   a. State: "Executing step [N]: [description]"

   b. Apply the change

   c. Run the step's success check command — show raw output

   d. If success check passes: "Step [N] complete." Proceed.

   e. If success check fails:
      - STOP — do not proceed to the next step
      - Execute this step's rollback command
      - Run the test suite to confirm system is back to pre-step state
      - Report the failure with full context and stop

10. **Run the full test suite every 3 steps**

---

### Phase 4: Verify

11. **Run the complete test suite** — all tests must pass

12. **Run migration-specific verification**
    - Schema migrations: confirm new schema is active, sample data is correct
    - Dependency upgrades: confirm new version is active, key API calls work
    - API migrations: confirm new endpoints work, old clients are updated or have compatibility

13. **Smoke test the primary affected feature**
    - Exercise the main use case end-to-end

14. **Validate rollback steps are still current**
    - Review the rollback plan — has anything changed that would invalidate a step?

---

### Phase 5: Rollback Plan Documentation

15. **Document the final rollback plan**
    - Exact commands in order
    - Data that would be reverted or lost
    - Estimated execution time

16. **Cleanup check**
    - Grep modified files for: `console.log`, `debugger`, `TODO`, `HACK`

17. **Final report**
    - What was migrated: [summary]
    - Files changed: [N]
    - Tests: [N] passing
    - Remaining risks: [list any known issues not resolved]
    - Rollback plan: [included in full]
