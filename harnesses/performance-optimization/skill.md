# Performance-Optimization Skill

Improve performance through measurement-driven cycles. Never optimize without a baseline. Never ship an optimization that breaks tests.

---

## Steps

1. **Establish baseline**
   - Run existing benchmarks (look for `benchmark`, `perf`, `bench` scripts)
   - If no benchmark exists: write a minimal timing harness for the hot path
   - Record: current latency (p50/p99), throughput (ops/sec), or memory (MB) — whichever is relevant
   - Document the baseline clearly before making any change

2. **Profile**
   - Use `cProfile`, `py-spy`, `perf`, `chrome://tracing`, or language-appropriate profiler
   - Identify the top 3 bottlenecks by time or memory contribution
   - Do not optimize based on intuition alone

3. **Hypothesize**
   - For each bottleneck, write a specific, falsifiable hypothesis:
     - "Replacing list lookup with a set will reduce `find_user` from O(n) to O(1), improving p99 by ~40%"
   - Order hypotheses by expected impact (highest first)

4. **Implement — one optimization at a time**
   - Pick the highest-impact hypothesis
   - Make only the change required to test this hypothesis
   - Do not clean up, refactor, or fix unrelated code in the same pass

5. **Measure**
   - Re-run the benchmark under the same conditions as the baseline
   - Record the new measurement
   - Compute the delta: `improvement = (baseline - new) / baseline * 100%`

6. **Accept or reject**
   - Accept if: improvement ≥ 5% and statistically reproducible (run 3 times)
   - Reject if: improvement < 5% or results are noisy — revert the change
   - Document the outcome regardless

7. **Verify correctness**
   - Run the full test suite
   - If any test fails: revert the optimization and mark the hypothesis as "breaks correctness"

8. **Repeat steps 4–7**
   - Work through remaining hypotheses in order
   - Stop when the performance target is met or all hypotheses are exhausted

9. **Report**
   - Baseline metrics
   - Each optimization attempted (accepted/rejected) with before/after measurements
   - Net improvement achieved
   - Remaining bottlenecks and why they were not pursued
