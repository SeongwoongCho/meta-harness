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
| [progressive-refinement](progressive-refinement.yaml) | Start rough, iteratively improve | progressive-refinement |
| [divide-and-conquer](divide-and-conquer.yaml) | Decompose, solve parts, merge | divide-and-conquer |
| [adversarial-review](adversarial-review.yaml) | Propose then attack your own work | adversarial-review |
| [spike-then-harden](spike-then-harden.yaml) | Quick prototype, then add quality | spike-then-harden |
| [bisect-and-isolate](bisect-and-isolate.yaml) | Binary search for root cause | systematic-debugging |
| [multi-lens-review](multi-lens-review.yaml) | Review from parallel independent lenses, synthesize by severity | code-review |
| [checkpoint-migrate](checkpoint-migrate.yaml) | Atomic reversible migration steps with per-step checkpoint and rollback | migration-safe |
| [scope-and-sprint](scope-and-sprint.yaml) | Triage scope to CORE/NICE/SKIP, implement only CORE, hand off with deferred list | rapid-prototype |
| [reproduce-hypothesize-verify](reproduce-hypothesize-verify.yaml) | Reproduce bug, form/test hypotheses with evidence, minimal fix, regression test | systematic-debugging |

All 14 patterns are instantiated as harnesses. The evolution manager may propose new genesis harnesses based on these patterns when evaluation data shows a matching failure signature.
