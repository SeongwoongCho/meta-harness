# Divide-and-Conquer Skill

Break the task into 2–5 independent sub-tasks, solve each in isolation with its own verification, then integrate the results and verify the system as a whole. Each sub-task boundary is an explicit contract — integration is a planned phase, not an afterthought.

---

## Steps

1. **Analyze — understand the full scope**
   - Read all files relevant to the task: source, tests, interfaces, configuration
   - Identify all modules, components, or concerns that the task touches
   - Map dependencies between them — find which changes are independent and which must be sequenced
   - Confirm there is no single atomic operation that would be simpler than decomposing

2. **Decompose — define 2–5 independent sub-tasks**
   - Split the work into sub-tasks with minimal overlap
   - For each sub-task, define: scope, inputs, outputs, and the interface contract it must satisfy
   - Order sub-tasks so that dependencies are resolved before dependents
   - If a sub-task touches more than 3 files, split it further
   - Document the decomposition plan before proceeding

3. **Solve sub-task 1 — implement and unit-verify**
   - Complete the first sub-task end-to-end
   - Write or update tests that verify the sub-task contract in isolation
   - Run only the tests for this sub-task — confirm green
   - Do not proceed to the next sub-task if this one is failing

4. **Solve remaining sub-tasks — one at a time**
   - Repeat the implement → test → confirm-green cycle for each remaining sub-task
   - Keep changes strictly scoped to the current sub-task
   - If a sub-task reveals that the decomposition was wrong, stop, revise the plan, and restart from step 2

5. **Integrate — combine sub-task results**
   - Merge all sub-task changes into a coherent whole
   - Resolve interface mismatches found at sub-task boundaries
   - Update integration-level tests (or write them if none exist) that exercise sub-tasks together
   - Run the full test suite — fix any failures before proceeding

6. **System verify — validate the integrated result**
   - Run the full test suite including integration tests — all must pass
   - Check that all sub-task contracts are satisfied end-to-end
   - Verify no unintended side effects across module boundaries
   - Run the build — confirm no compilation errors

7. **Final cleanup and report**
   - Grep all modified files for debug artifacts — remove any found
   - Confirm the decomposition plan was executed as defined
   - Report: sub-tasks completed, any decomposition changes made mid-execution, and integration issues encountered
