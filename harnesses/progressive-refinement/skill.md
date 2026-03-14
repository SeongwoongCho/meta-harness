# Progressive-Refinement Skill

Produce a working solution first, then iteratively improve the weakest quality dimension. Each pass is measured before and after to prevent regressions. Stop when all dimensions meet threshold or the budget is exhausted.

---

## Steps

1. **Rough pass — build a working solution**
   - Implement the simplest version that satisfies the core functional requirements
   - Do not optimize for quality dimensions yet — correctness only
   - Run tests to confirm the rough pass is functional
   - Record the baseline: note which quality dimensions are visibly weak

2. **Measure — score all quality dimensions**
   - Evaluate the implementation across all relevant dimensions: correctness, code quality, error handling, security, maintainability, test coverage
   - Assign a rough score (low / medium / high) to each dimension
   - List dimensions in ascending order of score (weakest first)
   - If all dimensions are already at medium or above, skip to step 8

3. **Identify the weakest dimension**
   - Select the lowest-scoring dimension from the ranked list
   - State explicitly: "Targeting dimension: X because score is Y"
   - If two dimensions tie, prioritize the one with higher user-visible impact

4. **Refine — improve the weakest dimension**
   - Make targeted changes to address only the selected dimension
   - Do not touch code unrelated to the target dimension
   - Write or update tests that verify the improvement

5. **Re-measure — verify improvement without regression**
   - Run the full test suite — confirm all existing tests still pass
   - Re-score the targeted dimension — confirm improvement
   - Re-score all other dimensions — confirm no regressions
   - If a regression is found: revert the change, record the conflict, move to the next weakest dimension

6. **Iterate (up to 5 passes)**
   - Repeat steps 3–5 for the next weakest dimension
   - Stop early if all dimensions reach medium or above
   - Track iteration count — do not exceed 5 refinement passes
   - After pass 5, proceed regardless of remaining scores

7. **Final test suite and build**
   - Run the complete test suite — all tests must pass
   - Run the build command — confirm no compilation errors
   - Grep modified files for debug artifacts: `console.log`, `debugger`, `TODO`, `HACK`, `FIXME` — remove any found

8. **Report**
   - List the rough-pass state vs final state for each quality dimension
   - State how many refinement passes were used and which dimension each targeted
   - Note any dimensions that remained below threshold and why further improvement was blocked
