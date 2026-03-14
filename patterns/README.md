# Workflow Design Patterns

This directory contains documented workflow design patterns for agent-based task execution. The evolution manager reads these patterns during Phase 2c (Concept-Level Reasoning) to propose genuinely novel harness structures.

Each pattern describes a reusable workflow structure, its strengths, failure signatures, and the conditions under which it should be applied.

## Pattern Index

| Pattern | Core Idea | Existing Harness |
|---------|-----------|-----------------|
| [converge-loop](converge-loop.yaml) | Iterate until acceptance criteria pass | ralph-loop |
| [red-green-refactor](red-green-refactor.yaml) | Test-first development cycle | tdd-driven |
| [hypothesis-cycle](hypothesis-cycle.yaml) | Scientific method for exploration | research-iteration |
| [mikado-method](mikado-method.yaml) | Atomic reversible refactoring steps | careful-refactor |
| [plan-then-execute](plan-then-execute.yaml) | Upfront planning with self-review | ralplan-consensus |
| [progressive-refinement](progressive-refinement.yaml) | Start rough, iteratively improve | *(none yet)* |
| [divide-and-conquer](divide-and-conquer.yaml) | Decompose, solve parts, merge | *(none yet)* |
| [adversarial-review](adversarial-review.yaml) | Propose then attack your own work | *(none yet)* |
| [spike-then-harden](spike-then-harden.yaml) | Quick prototype, then add quality | *(none yet)* |
| [bisect-and-isolate](bisect-and-isolate.yaml) | Binary search for root cause | systematic-debugging (partial) |

Patterns marked *(none yet)* are not instantiated as harnesses. The evolution manager may propose genesis based on these patterns when evaluation data shows a matching failure signature.
