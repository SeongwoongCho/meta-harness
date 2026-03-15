# Engineering Retro Skill

Weekly engineering retrospective. Analyzes commit history, work patterns, and code quality metrics with persistent history and trend tracking. Team-aware: identifies the current user, then analyzes every contributor with per-person praise and growth areas.

---

## Steps

### Phase 0: Parse Arguments

1. **Determine time window**
   - Default: 7 days
   - Accepted: `24h`, `14d`, `30d`, `Nw`, `compare`, `compare Nd`
   - If argument is invalid: show usage and stop

2. **Identify current user**
   - Run `git config user.name` and `git config user.email`
   - This person is "you" — the reader of this retro

---

### Phase 1: Gather Raw Data

3. **Run all git queries in parallel** (independent — run simultaneously)
   - All commits in window with stats: `git log origin/main --since="<window>" --format="%H|%aN|%ae|%ai|%s" --shortstat`
   - Per-author LOC breakdown with test vs production split
   - Commit timestamps for session detection (Pacific time via `TZ=America/Los_Angeles`)
   - File hotspots: files most frequently changed
   - Per-author commit counts: `git shortlog origin/main --since="<window>" -sn --no-merges`
   - Streak data: all unique commit dates going back from today

---

### Phase 2: Compute Metrics

4. **Build summary table**

   | Metric | Value |
   |--------|-------|
   | Commits to main | N |
   | Contributors | N |
   | PRs merged | N |
   | Net LOC added | N |
   | Test LOC ratio | N% |
   | Active days | N |
   | Sessions detected | N |
   | Avg LOC/session-hour | N |
   | Team shipping streak | Nd |

5. **Per-author leaderboard** (current user first, labeled "You (name)")

   ```
   Contributor         Commits   +/-          Top area
   You (alice)              32   +2400/-300   src/
   bob                      12   +800/-150    tests/
   ```

---

### Phase 3: Patterns and Velocity

6. **Commit-time distribution** (Pacific time)
   - Hourly histogram; identify peak hours, dead zones, late-night clusters
   - Session detection using 45-minute gap threshold
   - Classify: deep (50+ min), medium (20-50 min), micro (<20 min)

7. **Commit type breakdown**
   - Categorize by prefix: feat/fix/refactor/test/chore/docs
   - Show as percentage bar
   - Flag if fix ratio exceeds 50%

8. **Hotspot analysis**
   - Top 10 most-changed files
   - Flag files changed 5+ times (churn hotspots)

9. **Focus score and ship-of-the-week**
   - Focus score: % of commits touching the single most-changed top-level directory
   - Ship of the week: highest-LOC PR — title, LOC, why it matters

---

### Phase 4: Team Analysis

10. **Per-contributor section**

    For current user ("Your Week"):
    - Personal commit count, LOC, test ratio, session patterns
    - What you did well (2-3 specific things anchored in commits)
    - Where to level up (1-2 specific, actionable suggestions)

    For each teammate:
    - What they shipped (2-3 sentences on contributions and patterns)
    - Praise: 1-2 specific things, anchored in actual commits ("Cleaned up X in 3 small PRs")
    - Opportunity: 1 specific, framed as investment ("Test coverage on Y is 8% — worth investing before the next feature lands")

---

### Phase 5: History and Output

11. **Load prior retro history**
    - Check `ls .context/retros/*.json`
    - If found: load most recent, compute metric deltas, include "Trends vs Last Retro" table
    - If not found: skip comparison section

12. **Save JSON snapshot**
    - `mkdir -p .context/retros/`
    - Write `{today}-{n}.json` with metrics, authors, version range, streak, tweetable summary

13. **Write narrative to conversation**
    - Tweetable summary (first line)
    - Summary table with deltas if available
    - Time and session patterns
    - Shipping velocity
    - Code quality signals
    - Focus and highlights
    - Your Week (deep dive for current user)
    - Team Breakdown (per teammate)
    - Top 3 team wins
    - 3 things to improve
    - 3 habits for next week

---

## Rules

- Praise must be specific and anchored in actual commits — never generic ("great job")
- Growth suggestions must be framed as investment, not criticism
- Use `origin/main` for all git queries
- All timestamps in Pacific time
- Only the `.context/retros/` JSON is written to disk — everything else goes to the conversation
- If zero commits in window: say so and suggest a different window
