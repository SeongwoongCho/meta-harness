# Ship Workflow Skill

Fully automated ship workflow: merge main, run tests, review diff, bump version, update changelog, commit bisectable chunks, push, and create PR. Non-interactive — runs straight through and outputs the PR URL at the end.

---

## Steps

### Phase 0: Pre-flight

1. **Check the current branch**
   - Run `git branch --show-current`
   - If on `main`: STOP — "You're on main. Ship from a feature branch."

2. **Assess the changeset**
   - Run `git status` (never use `-uall`)
   - Run `git diff main...HEAD --stat` and `git log main..HEAD --oneline`
   - Uncommitted changes are always included — do not ask

---

### Phase 1: Merge and Test

3. **Merge origin/main**
   - Run `git fetch origin main && git merge origin/main --no-edit`
   - If simple conflicts (VERSION, CHANGELOG ordering): auto-resolve
   - If complex conflicts: STOP and show them

4. **Run the full test suite**
   - Run all available test commands (e.g., `npm test`, `pytest`, `go test ./...`)
   - If any test fails: show failures and STOP — do not proceed

---

### Phase 2: Pre-Landing Review

5. **Run two-pass review on the diff**
   - Run `git diff origin/main` to get the full diff
   - Pass 1 (CRITICAL): data safety, security, trust boundaries
   - Pass 2 (INFORMATIONAL): code quality, edge cases, test gaps

6. **Report all findings**
   - Always output ALL findings — critical and informational
   - For each CRITICAL issue: ask user — A) Fix now, B) Acknowledge, C) False positive
   - If user chose A (fix) on any issue: apply fixes, commit fixed files by name, STOP and ask user to re-run ship

7. **If only informational issues**: output them, continue to version bump

---

### Phase 3: Version and Changelog

8. **Auto-decide version bump**
   - Read the current VERSION file
   - Count diff lines: `git diff origin/main...HEAD --stat | tail -1`
   - MICRO: < 50 lines changed
   - PATCH: 50+ lines changed
   - MINOR / MAJOR: ask the user
   - Write new version to VERSION file

9. **Auto-generate CHANGELOG entry**
   - Run `git log main..HEAD --oneline` for all branch commits
   - Run `git diff main...HEAD` for full diff context
   - Categorize changes: Added / Changed / Fixed / Removed
   - Insert entry after header, dated today: `## [X.Y.Z] - YYYY-MM-DD`
   - Do NOT ask the user to describe changes — infer from diff and commits

---

### Phase 4: Commit, Push, PR

10. **Create bisectable commits**
    - Group changes into logical units (one coherent change per commit)
    - Commit ordering: infrastructure → models/services → controllers/views → VERSION+CHANGELOG
    - Each commit must be independently valid — no broken imports
    - Commit format: `<type>: <summary>` (feat/fix/chore/refactor/docs)

11. **Push to remote**
    - Run `git push -u origin <branch-name>`
    - Never force push

12. **Create PR**
    - Run `gh pr create` with title and body
    - PR body includes: summary bullets, pre-landing review findings, test results
    - **Output the PR URL** — this is the final output the user sees

---

## Rules

- Never skip tests — stop and show failures
- Never ask for confirmation except MINOR/MAJOR version bumps and CRITICAL review issues
- Always use bisectable commits — one logical change per commit
- Never force push
