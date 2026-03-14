# Spike-Then-Harden Skill

Build a fast, disposable prototype to learn the problem space, extract its learnings, then implement a production-quality version from scratch informed by what the spike revealed. The spike is a learning tool — it is never shipped.

---

## Steps

1. **Spike — build as fast as possible**
   - Implement the simplest path to a working prototype
   - Ignore tests, error handling, code quality, and edge cases
   - Use hardcoded values, direct coupling, and any shortcuts that save time
   - Stop when the spike demonstrates the core mechanic works end-to-end
   - Time-box the spike: if it takes more than 25% of the total budget, the task may be well-understood enough to skip the spike

2. **Verify the spike works (basic smoke test)**
   - Run the spike manually or with a single smoke test to confirm it does what was intended
   - Do not invest in spike test coverage — one confirmation is enough
   - If the spike fails: identify why, adjust the approach, re-spike (max 2 spike attempts)

3. **Assess — extract learnings from the spike**
   - Write down (in comments or a scratch note) what the spike revealed:
     - What was harder than expected?
     - What was easier than expected?
     - What architectural decisions did the spike reveal as wrong?
     - What interfaces or data shapes emerged naturally from the spike?
     - What edge cases surfaced during the spike?
   - Rate the spike's architecture: is it worth refactoring, or must it be discarded entirely?
   - Explicitly state: "The production design will differ from the spike in these ways: ..."

4. **Plan-production — design the production implementation**
   - Using the spike learnings, design the production architecture before writing any code
   - Define: module structure, interfaces, error handling strategy, test coverage targets
   - List the behaviors that must be tested (informed by spike-discovered edge cases)
   - Confirm the plan before proceeding — do not start implementation without a clear design

5. **Discard (or quarantine) the spike**
   - Delete spike files or move them to a clearly marked scratch location
   - Confirm the production implementation will be written fresh — not copied from the spike
   - If reusing spike code: document exactly which parts are being kept and why they meet production standards

6. **Harden — implement the production version**
   - Build the production implementation following the plan from step 4
   - Write tests for every behavior listed in the plan, including edge cases found during spike
   - Apply full error handling, input validation, and security practices
   - Run tests after each logical unit of work — do not accumulate failures

7. **Verify — confirm production version matches spike functionality**
   - Run the full test suite — all tests must pass
   - Verify every behavior the spike demonstrated is also covered by the production implementation
   - Run the build — confirm no errors
   - Grep modified files for debug artifacts: `console.log`, `debugger`, `TODO`, `HACK`, `FIXME` — remove any found

8. **Report**
   - State the key learnings extracted from the spike
   - List changes between spike architecture and production architecture
   - Note any spike edge cases that are now covered by production tests
   - Confirm the spike has been discarded or quarantined
