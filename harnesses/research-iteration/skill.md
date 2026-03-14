# Research Iteration Skill

Explore high-uncertainty problems through hypothesis-driven cycles. Measure everything. Document everything — including what failed.

---

## Steps

### Phase 0: Problem Framing

1. **Define the research question**
   - Restate the task as a research question: "Does [X] improve [metric] compared to [current approach]?"
   - Identify the primary success metric: a single quantitative measure (accuracy %, latency ms, memory MB, test pass rate)
   - Identify constraints that must not be violated (correctness, API compatibility, license)

2. **Understand the current system**
   - Glob to find relevant source files, benchmarks, and existing tests
   - Read the key implementation files to understand the current approach
   - Identify the measurement command (test runner, benchmark script, profiling command)

---

### Phase 1: Establish Baseline

3. **Run baseline measurement**
   - Execute the measurement command against the current implementation
   - Run 3 times if the metric varies (record average and variance)
   - Record: `Baseline: [metric] = [value ± variance]`

4. **Document current approach**
   - One paragraph: how does the current implementation work, and why does it work that way?
   - This is the "null hypothesis" — the starting point all experiments are compared against

---

### Phase 2: Hypothesis Cycles (repeat until budget reached or conclusion found)

5. **State the hypothesis**
   - "I believe [change X] will [improve/reduce/not affect] [metric] because [reasoning]"
   - Expected direction: better / worse / neutral
   - Expected magnitude: rough estimate (e.g., "5–20% improvement")

6. **Implement the experiment**
   - Change only the variable being tested — nothing else
   - Use descriptive naming to make the experiment variant identifiable
   - Keep the implementation minimal: enough to test the hypothesis, no more

7. **Measure the experiment**
   - Run the same measurement command used for the baseline
   - Run 3 times if the metric varies
   - Record raw numbers: `Experiment [N]: [metric] = [value ± variance]`

8. **Analyze the result**
   - Did the result match the hypothesis? (Yes / Partially / No)
   - Measured delta from baseline: +X% / -X% / no significant change
   - What does this tell us about the system?
   - Is this result statistically meaningful or within noise range?

9. **Decide: Continue / Pivot / Conclude**
   - **Continue**: this direction shows promise — refine the hypothesis and iterate
   - **Pivot**: this approach failed — form a new hypothesis based on what was learned
   - **Conclude**: sufficient evidence gathered — best result found, further iteration has diminishing returns

10. **Repeat steps 5–9**
    - Minimum 2 complete cycles before concluding
    - Maximum cycles constrained by budget (stop at 80% of token budget)

---

### Phase 3: Final Report

11. **Cycle summary table**
    - For each cycle: Hypothesis | Result | Delta from Baseline | Decision

12. **Best configuration found**
    - What is the best result achieved?
    - What configuration produced it?
    - Measured improvement over baseline (with concrete numbers)

13. **Confidence level**
    - High: 3+ consistent results supporting the conclusion
    - Medium: 2 results or consistent direction with some variance
    - Low: 1 result or inconsistent results

14. **Recommended next experiments**
    - Top 3 experiments that would increase confidence or explore adjacent improvements

15. **Negative results (refuted hypotheses)**
    - List each failed hypothesis and what it ruled out — these are valuable findings

16. **Code state verification**
    - Run the full test suite — all tests must pass
    - Run the build — no compilation errors
    - Confirm the codebase is in a clean, runnable state with the best experiment applied
    - Remove any experimental scaffolding not intended to be permanent
