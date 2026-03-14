# Adversarial-Review Skill

Complete the primary implementation, then switch roles: become an attacker whose goal is to break your own work. Write adversarial test cases, probe edge cases, attempt common exploit patterns, and challenge architectural decisions. Fix everything found. Repeat up to 3 attack-fix cycles.

---

## Steps

1. **Implement — complete the primary solution**
   - Build the full implementation as you normally would
   - Write standard tests for the happy path and documented edge cases
   - Run the full test suite — confirm all pass before starting the attack phase
   - Note the implementation boundaries: what it accepts, what it rejects, what it assumes

2. **Attack round 1 — break it with adversarial inputs**
   - Write adversarial test cases targeting:
     - Boundary values (zero, negative, max int, empty string, null, very large input)
     - Malformed input (unexpected types, missing fields, extra fields)
     - Common exploit patterns for the domain (injection, overflow, race conditions if concurrent)
     - Unicode, special characters, encoding edge cases
   - Run adversarial tests — record all failures
   - Challenge architectural decisions: "What if the upstream contract changes?", "What if this is called twice?"
   - List every issue found with severity: CRITICAL / HIGH / MEDIUM / LOW

3. **Fix — address all issues found in round 1**
   - Fix CRITICAL and HIGH issues first — do not proceed if any CRITICAL remains unfixed
   - For each fix: state the root cause, the fix applied, and which adversarial test now passes
   - Run the full test suite after all fixes — confirm no regressions

4. **Attack round 2 — re-attack with fresh adversarial tests**
   - Write new adversarial tests targeting the areas that were just fixed
   - Probe for fix regressions: does the fix introduce a new vulnerability?
   - Expand attack surface: what was not tested in round 1?
   - If no new issues found: proceed to step 6
   - If new issues found: record and continue to step 5

5. **Fix round 2 — address remaining issues**
   - Apply fixes for all round 2 findings
   - Run the full test suite — confirm green
   - If this is attack round 3 and issues remain: document them as known limitations, not silent failures

6. **Attack round 3 (final) — confirm stability**
   - One final adversarial pass focusing on any remaining weak areas
   - If issues are found and this is round 3: document them clearly, do not silently ignore
   - Run the full test suite — all tests must pass including adversarial ones

7. **Final verification**
   - Run the complete test suite — all tests (standard + adversarial) must pass
   - Run the build command — no errors
   - Grep modified files for debug artifacts: `console.log`, `debugger`, `TODO`, `HACK`, `FIXME` — remove any found

8. **Report**
   - List all adversarial test cases written and their outcomes
   - State each issue found by severity and whether it was fixed or deferred
   - Note any architectural concerns raised that could not be fixed within scope
   - State how many attack rounds were completed
