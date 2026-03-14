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

Each protocol lives in `{plugin_root}/protocols/{protocol-name}/` and contains one file (read plugin root from `.meta-harness/.plugin-root`):

```
{plugin_root}/protocols/
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
# These 6 dimensions are task-agnostic — they apply to code, research, docs, planning, etc.
universal_dimensions:
  correctness:
    weight: 0.25
    description: "Output satisfies stated requirements (code works, analysis answers the question, docs are accurate)"
    evidence_sources: ["bash_output", "diff", "file_read"]
    scoring_guide: "1.0 = all requirements met, 0.7 = mostly correct with minor gaps, 0.4 = partially correct, 0.0 = fundamentally wrong"

  completeness:
    weight: 0.20
    description: "Output covers the full scope of the task with no obvious gaps"
    evidence_sources: ["diff", "file_read"]
    scoring_guide: "1.0 = all aspects addressed, 0.7 = main points covered, 0.4 = significant gaps, 0.0 = barely started"

  quality:
    weight: 0.20
    description: "Structural and stylistic quality (clean code, rigorous analysis, coherent writing)"
    evidence_sources: ["diff", "bash_output"]
    scoring_guide: "1.0 = exemplary craft, 0.7 = good with minor issues, 0.4 = functional but rough, 0.0 = poor quality"

  robustness:
    weight: 0.10
    description: "Handles edge cases, failure modes, counterarguments, or limitations"
    evidence_sources: ["diff", "test_output"]
    scoring_guide: "1.0 = comprehensive edge case handling, 0.5 = basic coverage, 0.0 = fragile/no consideration"

  clarity:
    weight: 0.15
    description: "Communicates intent clearly (readable code, understandable docs, clear reasoning)"
    evidence_sources: ["diff", "file_read"]
    scoring_guide: "1.0 = immediately clear, 0.7 = clear with minor ambiguity, 0.4 = confusing in parts, 0.0 = opaque"

  verifiability:
    weight: 0.10
    description: "Output can be independently verified (tests exist, evidence provided, claims checkable)"
    evidence_sources: ["bash_output", "diff"]
    scoring_guide: "1.0 = fully verifiable, 0.7 = mostly verifiable, 0.4 = partially, 0.0 = unverifiable claims"

# Custom dimensions (domain-specific, add up with universal to total 1.0)
custom_dimensions:
  my_custom_dim:
    weight: 0.25
    description: "What this dimension measures"
    evidence_sources: ["bash_output", "diff", "file_read"]
    scoring_guide: "How to score 0.0 to 1.0"

# Quality gates (hard thresholds — if any gate fails, overall evaluation fails)
quality_gates:
  - dimension: correctness
    min_score: 0.5
    message: "Output must be at least partially correct"
  - overall_score:
    min_score: 0.6
    message: "Overall score must be at least 0.6"
```

**Weight constraint:** All `universal_dimensions` weights + all `custom_dimensions` weights must sum to exactly `1.0`.

---

## Step-by-Step: Creating a Custom Protocol

### Step 1: Identify Your Domain

Determine the domain of evaluation. Built-in protocols for reference:
- `universal-standard` — Task-agnostic baseline (correctness, completeness, quality, robustness, clarity, verifiability). Good starting point for any domain.
- `research-standard` — Adds analysis_depth, methodology_rigor, actionability for deep research tasks
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

Example weight redistribution for ML research (based on universal-standard):
```yaml
# Universal dims reduced to 0.40 total
correctness:   0.10
completeness:  0.08
quality:       0.08
robustness:    0.06
clarity:       0.05
verifiability: 0.03
# Custom dims = 0.60 total
model_accuracy: 0.25
training_efficiency: 0.15
reproducibility: 0.12
experiment_tracking: 0.08
```

### Step 4: Define Quality Gates

Every protocol should have at minimum:
- A gate on `correctness` (min 0.5 — output must be at least partially correct)
- A gate on `overall_score` (min 0.5 to 0.7 depending on domain risk)

For high-stakes domains (migrations, security-sensitive):
- Add gates on specific critical dimensions (e.g., `robustness: min 0.8`)

### Step 5: Write Scoring Guides

Each dimension needs a `scoring_guide` that the evaluator agent uses to assign a 0.0–1.0 score. Be specific:
- State what a 1.0 looks like
- State what a 0.0 looks like
- State what a 0.5 looks like
- List the evidence sources the agent should examine

### Step 6: Create the Protocol File

Create `{plugin_root}/protocols/{your-protocol-name}/protocol.yaml` following the schema above (read plugin root from `.meta-harness/.plugin-root`).

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
    backend: universal-standard
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
  correctness:
    weight: 0.25
    description: "Output satisfies stated requirements"
    evidence_sources: ["bash_output", "diff", "file_read"]
    scoring_guide: "1.0 = all requirements met, 0.0 = fundamentally wrong"
  completeness:
    weight: 0.20
    description: "Covers the full scope of the task"
    evidence_sources: ["diff", "file_read"]
    scoring_guide: "1.0 = all aspects addressed, 0.0 = barely started"
  quality:
    weight: 0.20
    description: "Structural and stylistic quality"
    evidence_sources: ["diff", "bash_output"]
    scoring_guide: "1.0 = exemplary, 0.0 = poor"
  robustness:
    weight: 0.10
    description: "Handles edge cases and failure modes"
    evidence_sources: ["diff", "test_output"]
    scoring_guide: "1.0 = comprehensive, 0.0 = fragile"
  clarity:
    weight: 0.15
    description: "Communicates intent clearly"
    evidence_sources: ["diff", "file_read"]
    scoring_guide: "1.0 = immediately clear, 0.0 = opaque"
  verifiability:
    weight: 0.10
    description: "Can be independently verified"
    evidence_sources: ["bash_output", "diff"]
    scoring_guide: "1.0 = fully verifiable, 0.0 = unverifiable"

custom_dimensions:
  # Define your custom dimensions here (total weight must bring sum to 1.0)
  # Reduce universal dim weights to make room for custom dims
  # example_dimension:
  #   weight: 0.00   # adjust universal weights down to compensate
  #   description: "What this measures"
  #   evidence_sources: ["bash_output"]
  #   scoring_guide: "1.0 = ..., 0.5 = ..., 0.0 = ..."

quality_gates:
  - dimension: correctness
    min_score: 0.5
    message: "Output must be at least partially correct"
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
