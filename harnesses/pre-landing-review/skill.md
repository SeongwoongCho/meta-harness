# Pre-Landing Review Skill

Analyze the current branch's diff against main for structural issues that tests don't catch. Two-pass review: Critical issues block merge; Informational issues are advisory. Read-only by default — only modifies files if user explicitly chooses to fix a critical issue.

---

## Steps

### Phase 0: Setup

1. **Check branch and diff**
   - Run `git branch --show-current`
   - If on `main`: output "Nothing to review — you're on main or have no changes against main." and stop
   - Run `git fetch origin main --quiet && git diff origin/main --stat`
   - If no diff: output same message and stop

2. **Get the full diff**
   - Run `git fetch origin main --quiet`
   - Run `git diff origin/main` to get both committed and uncommitted changes against latest main

---

### Phase 1: Two-Pass Review

3. **Pass 1 — CRITICAL issues**

   Review for high-severity structural problems:
   - **Data safety**: unguarded deletes/updates, missing transactions, unsafe bulk ops
   - **Security**: unsanitized user input used in queries/commands, hardcoded secrets, weak auth
   - **Trust boundary violations**: user-controlled data flowing into privileged operations without validation
   - **Injection risks**: SQL, shell, template injection vectors

4. **Pass 2 — INFORMATIONAL issues**

   Review for advisory issues:
   - **Conditional side effects**: functions with hidden side effects based on state
   - **Magic numbers and string coupling**: hardcoded values that should be constants
   - **Dead code**: unreachable branches, unused variables, stale imports
   - **Test gaps**: new codepaths with no corresponding tests
   - **Error handling**: missing error cases, swallowed exceptions
   - **Code smells**: long functions, repeated logic, unclear naming

---

### Phase 2: Output Findings

5. **Output all findings**
   - Always output ALL findings — critical and informational
   - Summary header: `Pre-Landing Review: N issues (X critical, Y informational)`
   - Format each finding: `[SEVERITY] file:line — problem description. Fix: one-line fix suggestion.`

6. **Handle critical issues**
   - For each CRITICAL issue: ask user individually:
     - The problem (file:line + description)
     - Your recommended fix
     - Options: A) Fix it now (recommended), B) Acknowledge and ship anyway, C) False positive — skip
   - If user chose A (fix): apply only the recommended fixes to the specific files, then STOP and tell user to re-run the review
   - If user chose only B or C on all critical issues: continue

7. **Finish**
   - Output informational findings
   - Report is complete — do not commit, push, or create PRs

---

## Rules

- Read-only by default — never modify files unless user chooses Fix
- Never commit, push, or create PRs
- Be terse: one line problem, one line fix. No preamble
- Only flag real problems — skip anything that is fine
- Read the FULL diff before commenting — do not flag issues already addressed in the diff
