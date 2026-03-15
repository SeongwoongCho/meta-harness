# QA Testing Skill

Systematically QA test an application like a real user. Click everything, fill every form, check every state. Produce a structured report with health score and evidence. Four modes: diff-aware (automatic on feature branches), full (systematic exploration), quick (30-second smoke test), and regression (compare against baseline).

---

## Steps

### Phase 0: Setup

1. **Parse request parameters**
   - Target URL (required, or auto-detect in diff-aware mode)
   - Mode: `full` (default when URL given), `--quick`, `--regression <baseline>`, or diff-aware (no URL on feature branch)
   - Auth credentials (if specified)
   - Output directory: `qa-reports/` (default)

2. **Diff-aware mode** (automatic when on feature branch with no URL)
   - Run `git diff main...HEAD --name-only` and `git log main..HEAD --oneline`
   - Identify affected pages/routes from changed files
   - Detect running app: try `http://localhost:3000`, then `:4000`, then `:8080`
   - If no local app found: ask user for URL

---

### Phase 1: Initialize and Authenticate

3. **Create output directories**
   - `mkdir -p qa-reports/screenshots`

4. **Authenticate if needed**
   - Navigate to login URL, fill credentials (write `[REDACTED]` for passwords in all outputs)
   - Verify login succeeded
   - If 2FA required: ask user for code and wait

---

### Phase 2: Orient

5. **Map the application**
   - Navigate to target URL; take annotated initial screenshot
   - Map navigation links
   - Check console for errors on landing
   - Detect framework (Next.js, Rails, SPA, etc.) — note in report

---

### Phase 3: Explore

6. **Explore each page systematically**

   At each page:
   - Take annotated screenshot
   - Check console for errors
   - Visual scan: layout, rendering, broken images
   - Interactive elements: click buttons, links, controls
   - Forms: fill and submit; test empty, invalid, edge cases
   - States: empty, loading, error, overflow
   - Responsiveness: check mobile viewport if relevant

   Depth judgment: spend more time on core features (dashboard, search, checkout) and less on secondary pages (about, terms).

7. **Quick mode** (`--quick`)
   - Visit homepage + top 5 navigation targets only
   - Check: page loads? Console errors? Broken links visible?
   - Skip per-page checklist

---

### Phase 4: Document

8. **Document each issue immediately when found**
   - Every issue requires at least one screenshot — no exceptions
   - Verify before documenting: retry once to confirm reproducibility
   - Interactive bugs: screenshot before + screenshot after action
   - Static bugs: single annotated screenshot

   Issue format:
   ```
   **ISSUE-NNN** [Severity] [Category]
   Title: one-line description
   URL: page where found
   Repro: step-by-step instructions
   Expected: what should happen
   Actual: what happens instead
   Screenshot: path/to/screenshot.png
   ```

---

### Phase 5: Report

9. **Compute health score**

   Category scores (start at 100, deduct per finding):
   - Critical issue: -25, High: -15, Medium: -8, Low: -3

   | Category | Weight |
   |----------|--------|
   | Functional | 20% |
   | Accessibility | 15% |
   | UX | 15% |
   | Console | 15% |
   | Links | 10% |
   | Performance | 10% |
   | Visual | 10% |
   | Content | 5% |

   Console score: 0 errors=100, 1-3=70, 4-10=40, 10+=10.

10. **Write report**
    - Health score (0-100)
    - Top 3 things to fix
    - Console health summary
    - Per-issue list with evidence
    - Pages visited, screenshot count, duration

11. **Save baseline JSON**
    - Write `qa-reports/baseline.json` with date, URL, health score, issue list

12. **Regression mode** (if `--regression <baseline>` provided)
    - Load baseline file
    - Compare: issues fixed, new issues, score delta
    - Append regression section to report

---

## Rules

- Repro is everything — every issue needs at least one screenshot
- Never read source code — test as a user, not a developer
- Check console after every interaction
- Write `[REDACTED]` for all passwords in repro steps and reports
- Document incrementally — write each issue as found, not at the end
- Depth over breadth: 5-10 well-documented issues beat 20 vague ones
