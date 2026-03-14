---
name: protocol-authoring
description: "Guide for creating custom evaluation protocols for meta-harness. Use when user wants to define new evaluation criteria."
---

# Protocol Authoring Guide

## Purpose

Evaluation protocols are independent from harnesses. A protocol defines *what success means* — the scoring dimensions, their weights, and quality gates. Harnesses define *how to work*. The same harness can be evaluated by different protocols depending on the project domain.

Use this skill when the user wants to create a custom evaluation protocol for their specific domain (e.g., data science accuracy, API SLA compliance, accessibility standards).

---

## Protocol Structure

Each protocol lives in `protocols/{protocol-name}/` and contains one file:

```
protocols/
  my-protocol/
    protocol.yaml        # Scoring dimensions, weights, quality gates
```

No scripts are needed — the evaluator agent (LLM) performs all scoring using the protocol definition + collected evidence from hooks.

---

## protocol.yaml Schema

```yaml
name: my-protocol
description: "One-line description of what this protocol evaluates"
version: "1.0"
domain: general          # backend | frontend | ml | cli | infra | general

# Universal dimensions (always present, re-weighted to accommodate custom dims)
universal_dimensions:
  build_success:
    weight: 0.15
    description: "Code builds/compiles without errors"
    evidence_sources: ["bash_output"]
    scoring_guide: "1.0 = clean build, 0.0 = build fails, 0.5 = warnings only"

  test_pass_rate:
    weight: 0.15
    description: "Automated tests pass"
    evidence_sources: ["bash_output"]
    scoring_guide: "Score = passing_tests / total_tests. 1.0 = all pass."

  code_quality:
    weight: 0.10
    description: "Code quality (lint, complexity, duplication)"
    evidence_sources: ["bash_output", "diff"]
    scoring_guide: "1.0 = no lint errors, clean diff. Deduct for complexity."

  robustness:
    weight: 0.08
    description: "Error handling, edge cases covered"
    evidence_sources: ["diff", "test_output"]
    scoring_guide: "1.0 = all error paths handled, 0.5 = basic handling, 0.0 = none"

  maintainability:
    weight: 0.07
    description: "Code is easy to understand and modify"
    evidence_sources: ["diff"]
    scoring_guide: "Assess naming clarity, function size, separation of concerns"

  security:
    weight: 0.07
    description: "No introduced security vulnerabilities"
    evidence_sources: ["diff", "bash_output"]
    scoring_guide: "1.0 = no issues, 0.0 = critical vulnerability introduced"

  readability:
    weight: 0.07
    description: "Code reads naturally, comments where needed"
    evidence_sources: ["diff"]
    scoring_guide: "Assess variable names, function names, inline comments"

  error_handling:
    weight: 0.06
    description: "Errors surfaced and handled gracefully"
    evidence_sources: ["diff", "bash_output"]
    scoring_guide: "1.0 = all errors handled with user-friendly messages"

# Custom dimensions (domain-specific, add up with universal to total 1.0)
custom_dimensions:
  my_custom_dim:
    weight: 0.25
    description: "What this dimension measures"
    evidence_sources: ["bash_output", "diff", "file_read"]
    scoring_guide: "How to score 0.0 to 1.0"

# Quality gates (hard thresholds — if any gate fails, overall evaluation fails)
quality_gates:
  - dimension: build_success
    min_score: 1.0
    message: "Build must succeed"
  - dimension: test_pass_rate
    min_score: 0.8
    message: "At least 80% of tests must pass"
  - overall_score:
    min_score: 0.6
    message: "Overall score must be at least 0.6"
```

**Weight constraint:** All `universal_dimensions` weights + all `custom_dimensions` weights must sum to exactly `1.0`.

---

## Step-by-Step: Creating a Custom Protocol

### Step 1: Identify Your Domain

Determine the domain of evaluation. Built-in protocols for reference:
- `code-quality-standard` — General software quality (good baseline)
- `ml-research` — ML accuracy, training efficiency, reproducibility
- `web-app-performance` — Response time, UI consistency, Lighthouse score
- `cli-tool-ux` — UX quality, error messages, help text, documentation

### Step 2: Define Custom Dimensions

Ask: "What does success look like that isn't captured by universal dimensions?"

Examples:
- For ML: `model_accuracy`, `training_efficiency`, `reproducibility`, `experiment_tracking`
- For APIs: `response_time_p99`, `contract_conformance`, `backward_compatibility`
- For data pipelines: `data_integrity`, `idempotency`, `schema_conformance`

### Step 3: Assign Weights

Rules:
1. Custom dimensions should total no more than 0.60 (leave room for universal dims)
2. The most important custom dimension should have weight ≥ 0.15
3. Universal dims that are less relevant can be reduced to as low as 0.03
4. Total must be exactly 1.0

Example weight redistribution for ML research:
```yaml
# Universal dims reduced to 0.40 total
build_success: 0.08
test_pass_rate: 0.08
code_quality: 0.06
robustness: 0.05
maintainability: 0.05
security: 0.04
readability: 0.03
error_handling: 0.01
# Custom dims = 0.60 total
model_accuracy: 0.25
training_efficiency: 0.15
reproducibility: 0.12
experiment_tracking: 0.08
```

### Step 4: Define Quality Gates

Every protocol should have at minimum:
- A gate on `build_success` (min 1.0 for compiled languages, 0.8 for interpreted)
- A gate on `overall_score` (min 0.5 to 0.7 depending on domain risk)

For high-stakes domains (migrations, security-sensitive):
- Add gates on specific critical dimensions (e.g., `security: min 0.9`)

### Step 5: Write Scoring Guides

Each dimension needs a `scoring_guide` that the evaluator agent uses to assign a 0.0–1.0 score. Be specific:
- State what a 1.0 looks like
- State what a 0.0 looks like
- State what a 0.5 looks like
- List the evidence sources the agent should examine

### Step 6: Create the Protocol File

Create `protocols/{your-protocol-name}/protocol.yaml` following the schema above.

Then register it in `.meta-harness/config.yaml` if you want it as the default for your project:

```yaml
evaluation:
  default_protocol: my-protocol
```

Or bind it to specific task types:
```yaml
evaluation:
  protocol_bindings:
    ml: ml-research
    backend: code-quality-standard
    general: my-protocol
```

---

## Template: Minimal Custom Protocol

Copy this template and fill in your custom dimensions:

```yaml
name: REPLACE_ME
description: "REPLACE_ME"
version: "1.0"
domain: general

universal_dimensions:
  build_success:
    weight: 0.15
    description: "Code builds without errors"
    evidence_sources: ["bash_output"]
    scoring_guide: "1.0 = clean build, 0.0 = build fails"
  test_pass_rate:
    weight: 0.15
    description: "Automated tests pass"
    evidence_sources: ["bash_output"]
    scoring_guide: "Score = passing / total"
  code_quality:
    weight: 0.10
    description: "Lint and complexity clean"
    evidence_sources: ["bash_output", "diff"]
    scoring_guide: "1.0 = no issues"
  robustness:
    weight: 0.07
    description: "Error handling covered"
    evidence_sources: ["diff"]
    scoring_guide: "1.0 = all paths handled"
  maintainability:
    weight: 0.06
    description: "Code easy to modify"
    evidence_sources: ["diff"]
    scoring_guide: "Assess naming and structure"
  security:
    weight: 0.06
    description: "No vulnerabilities introduced"
    evidence_sources: ["diff"]
    scoring_guide: "1.0 = no issues"
  readability:
    weight: 0.05
    description: "Code reads naturally"
    evidence_sources: ["diff"]
    scoring_guide: "Assess naming clarity"
  error_handling:
    weight: 0.05
    description: "Errors handled gracefully"
    evidence_sources: ["diff", "bash_output"]
    scoring_guide: "1.0 = all errors handled"

custom_dimensions:
  # Define your custom dimensions here (total weight must bring sum to 1.0)
  # example_dimension:
  #   weight: 0.31
  #   description: "What this measures"
  #   evidence_sources: ["bash_output"]
  #   scoring_guide: "1.0 = ..., 0.5 = ..., 0.0 = ..."

quality_gates:
  - dimension: build_success
    min_score: 1.0
    message: "Build must succeed"
  - overall_score:
    min_score: 0.6
    message: "Overall score must be at least 0.6"
```

---

## Validation Checklist

Before using a custom protocol, verify:
- [ ] All dimension weights sum to exactly 1.0
- [ ] Every dimension has a `scoring_guide`
- [ ] Every dimension has at least one `evidence_source`
- [ ] Quality gates reference valid dimension names
- [ ] Protocol name matches the directory name
- [ ] Protocol is referenced in `.meta-harness/config.yaml` or in a harness `contract.yaml`
