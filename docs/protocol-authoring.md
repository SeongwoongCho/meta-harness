# Evaluation Protocol Authoring Guide

An evaluation protocol defines *what success means* for a task. It is a first-class object
independent from harnesses — the same harness can be scored by different protocols depending
on the domain and context.

This guide covers everything you need to create a custom evaluation protocol.

---

## What an Evaluation Protocol Is

A protocol specifies:

1. **Dimensions** — what aspects of the result to score
2. **Weights** — how much each dimension contributes to the overall score
3. **Types** — how each dimension is measured (binary, percentage, score)
4. **Quality gates** — thresholds that must be met for the evaluation to pass

The evaluator agent reads the protocol definition and scores the task result using
evidence collected during execution (build output, test results, lint output, code diffs).
**No scoring scripts are required** — all scoring reasoning is performed by the evaluator
agent.

---

## Directory Structure

```
protocols/your-protocol-name/
└── protocol.yaml
```

Only one file is required. The evaluator agent reads `protocol.yaml` and applies it.

---

## `protocol.yaml` Reference

### Complete Example

```yaml
# ─────────────────────────────────────────────
# Identity
# ─────────────────────────────────────────────
name: your-protocol-name
version: 1.0.0
description: "What domain or use case this protocol evaluates. One sentence."

# ─────────────────────────────────────────────
# Universal Dimensions
# ─────────────────────────────────────────────
# These 6 dimensions are present in every protocol.
# You MUST include all 6. You may re-weight them to accommodate custom dimensions,
# but they must all be present with weight > 0.
#
# CONSTRAINT: sum of ALL universal_dimensions weights
#           + sum of ALL custom_dimensions weights = 1.0 exactly
#
universal_dimensions:
  - name: correctness
    weight: 0.20          # Default: 0.25. Reduced here to make room for custom dims.
    type: score_0_to_1
    description: "Output satisfies stated requirements"
    scoring_guide: "1.0 if all requirements met with no errors. 0.7 if most requirements
                    met with minor gaps. 0.4 if significant gaps. 0.0 if output fails
                    to address the stated task."

  - name: completeness
    weight: 0.15
    type: score_0_to_1
    description: "Output covers the full scope of the task"
    scoring_guide: "1.0 if full scope addressed. 0.7 if most scope covered, minor gaps
                    acknowledged. 0.4 if significant portions of scope unaddressed.
                    0.0 if task is barely started or major scope missing."

  - name: quality
    weight: 0.15
    type: score_0_to_1
    description: "Structural and stylistic quality of the output"
    scoring_guide: "Consider: clean structure, appropriate naming, no unnecessary
                    complexity, follows established patterns. Score 0.7 as baseline
                    for clean but unremarkable output."

  - name: robustness
    weight: 0.10
    type: score_0_to_1
    description: "Handles edge cases, failure modes, and adversarial conditions"
    scoring_guide: "Score based on: error handling present, boundary conditions handled,
                    limitations acknowledged. Deduct for each obvious unhandled edge case."

  - name: clarity
    weight: 0.10
    type: score_0_to_1
    description: "Output clearly communicates its intent and reasoning"
    scoring_guide: "Consider: readable structure, meaningful names, non-obvious logic
                    explained. Score 0.7 for generally clear output with some ambiguous
                    sections."

  - name: verifiability
    weight: 0.05
    type: score_0_to_1
    description: "Output can be independently verified"
    scoring_guide: "1.0 if fully verifiable with clear evidence or acceptance criteria.
                    0.7 if mostly verifiable, some claims require trust. 0.0 if no
                    way to verify correctness."

# ─────────────────────────────────────────────
# Custom Dimensions
# ─────────────────────────────────────────────
# Domain-specific dimensions that matter for this protocol.
# Add as many as needed, but ensure total weight sums to 1.0.
#
custom_dimensions:
  - name: your_custom_metric
    weight: 0.15
    type: score_0_to_1
    description: "What this dimension measures"
    scoring_guide: "How the evaluator agent should assign a score. Be specific:
                    what evidence to look for, what constitutes a high score vs.
                    a low score. The evaluator agent reads this field directly."

  - name: another_custom_metric
    weight: 0.15
    type: score_0_to_1
    description: "Another domain-specific dimension"
    scoring_guide: "Scoring instructions for this dimension."

# ─────────────────────────────────────────────
# Quality Gates
# ─────────────────────────────────────────────
quality_gates:
  minimum_overall_score: 0.65     # Evaluation fails if weighted score < this value
  required_passing_dimensions:
    - correctness                 # These dimensions must individually score >= 0.5
    # - completeness              # Add dimensions that are non-negotiable

  hooks:
    role: early_warning
    checks:
      - lint                      # Run linter before evaluation
      - type_check                # Run type checker before evaluation

  ci:
    role: final_authority
    outputs:
      - structured_json_report    # Evaluator agent outputs structured JSON
```

---

## Universal Dimensions

These 6 dimensions are present in every protocol with their default weights:

| Dimension | Default Weight | Type | What it measures |
|-----------|---------------|------|-----------------|
| `correctness` | 0.25 | score_0_to_1 | Does the output satisfy requirements? |
| `completeness` | 0.20 | score_0_to_1 | Does the output cover the full scope? |
| `quality` | 0.20 | score_0_to_1 | Structural and stylistic quality |
| `robustness` | 0.10 | score_0_to_1 | Edge case and failure mode handling |
| `clarity` | 0.15 | score_0_to_1 | Clear communication of intent |
| `verifiability` | 0.10 | score_0_to_1 | Can the output be independently verified? |

Default total: **1.00**

When you add custom dimensions, you must reduce universal dimension weights to maintain
the 1.0 sum. The typical approach is to reduce `correctness` and `completeness`
proportionally since they dominate the default weighting.

---

## Dimension Types

| Type | Range | Description | When to use |
|------|-------|-------------|-------------|
| `binary` | `0.0` or `1.0` | Pass/fail only | Go/no-go criteria (build passes, deployment succeeds) |
| `percentage` | `0.0` to `1.0` | Continuous 0%–100% | Coverage, test pass rate, benchmark scores |
| `score_0_to_1` | `0.0` to `1.0` | Evaluator judgment | Qualitative assessments (correctness, clarity, quality) |

---

## Weight Constraints

**The total of all dimension weights must sum exactly to 1.0.**

This constraint is validated at protocol load time. If the sum is not 1.0, the protocol
will fail to load.

**Recommended weight budget allocation:**

| Scenario | Universal dims | Custom dims | Notes |
|----------|---------------|-------------|-------|
| General purpose (no custom) | 1.00 | 0 | Use `universal-standard` |
| One important custom dim | 0.70 | 0.30 | Reduce correctness/completeness proportionally |
| Two important custom dims | 0.55 | 0.45 | Split reductions across all 6 dims |
| Three+ custom dims | 0.40 | 0.60 | Keep each universal dim above 0.05 |

---

## Writing Effective `scoring_guide` Fields

The `scoring_guide` field is read by the evaluator agent to understand how to score each
dimension. Write it as instructions to the evaluator:

**Poor (too vague):**
```yaml
scoring_guide: "Score based on quality"
```

**Good (specific and actionable):**
```yaml
scoring_guide: "Score based on Lighthouse performance score if available in evidence.
                Score = lighthouse_score / 100. If no Lighthouse data, estimate from:
                - No render-blocking resources (0.3 contribution)
                - Images are optimized (0.3 contribution)
                - JavaScript bundle < 200KB (0.4 contribution).
                Score 0.5 as neutral if no performance evidence available."
```

The more specific your scoring guide, the more consistent the evaluator's scores will be
across sessions.

---

## Built-in Protocol Designs

Study these for patterns you can adapt:

### `universal-standard` — No custom dimensions

All 6 universal dimensions at default weights. Use as the baseline.
Best for: any task type without strong domain-specific quality criteria.

### `ml-research` — Research quality emphasis

Universal dims re-weighted to 0.50 total. Custom dims (0.50 total):
- `model_accuracy` (0.25) — primary ML quality signal
- `training_efficiency` (0.15) — training time and resource use
- `reproducibility` (0.15) — reproducible results with fixed seed
- `experiment_tracking` (0.10) — experiment logged in tracking system (MLflow, W&B, etc.)

### `web-app-performance` — Performance and UX emphasis

Universal dims re-weighted to 0.45 total. Custom dims (0.55 total):
- `response_time` (0.20) — API and page load response times
- `ui_consistency` (0.15) — visual consistency across the app
- `accessibility` (0.10) — WCAG compliance and screen reader support
- `lighthouse_score` (0.10) — Lighthouse CI performance score

### `cli-tool-ux` — Developer experience emphasis

Universal dims re-weighted to 0.45 total. Custom dims (0.55 total):
- `ux_quality` (0.20) — CLI ergonomics (flag naming, help text, output format)
- `error_messages` (0.15) — error messages are actionable and specific
- `help_text` (0.10) — `--help` output is complete and accurate
- `documentation_coverage` (0.10) — README and man page coverage

---

## Testing Your Protocol

### 1. Validate weights sum to 1.0

```bash
python3 -c "
import yaml
with open('protocols/your-protocol-name/protocol.yaml') as f:
    p = yaml.safe_load(f)
total = sum(d['weight'] for d in p['universal_dimensions'])
total += sum(d['weight'] for d in p.get('custom_dimensions', []))
print(f'Total weight: {total:.4f} — {\"PASS\" if abs(total - 1.0) < 0.001 else \"FAIL\"}')"
```

### 2. Bind to an existing harness and run

```
/meta-harness-eval --protocol=your-protocol-name --session=last
```

This re-evaluates the most recent session using your protocol.

### 3. Compare with `universal-standard`

Run the same task twice with different protocols and compare scores:

```
/meta-harness-run --protocol=universal-standard "your test task"
/meta-harness-run --protocol=your-protocol-name "your test task"
```

If the scores are identical across all tasks, your custom dimensions may not be adding
signal. Investigate whether the evidence collected is sufficient for the evaluator to
score your custom dimensions.

---

## Protocol Naming Conventions

| Pattern | Example | When to use |
|---------|---------|-------------|
| `{domain}-{aspect}` | `ml-research`, `web-app-performance` | Domain-specific protocols |
| `{aspect}-standard` | `universal-standard` | General-purpose baselines |
| `{tool}-{aspect}` | `cli-tool-ux` | Tool category protocols |

Use lowercase kebab-case. The name must be unique across all protocols in the pool.

---

## Common Pitfalls

**Pitfall 1: Custom dimensions with no evidence**

If the evaluator agent has no evidence to score a custom dimension (e.g., no Lighthouse
report was generated), it will score 0.5 as neutral. This dilutes the signal from your
custom dimension. Solution: ensure the harness's `verification_steps` generate the
evidence your protocol needs.

**Pitfall 2: Too many custom dimensions**

Adding 5+ custom dimensions at 0.10 weight each gives each one equal importance to
`verifiability` in the default protocol. The result is a protocol that measures
everything and prioritizes nothing. Focus on 2-3 custom dimensions that genuinely
differentiate your domain.

**Pitfall 3: Vague scoring guides for qualitative dimensions**

`type: score_0_to_1` dimensions require the evaluator to exercise judgment. If the
`scoring_guide` is vague, scores will vary widely across sessions. Write scoring guides
as rubrics: what does a 0.9 look like? What does a 0.5 look like? What does a 0.2
look like?

**Pitfall 4: Requiring dimensions the evaluator cannot observe**

If your dimension requires measuring "user satisfaction" or "business impact", the
evaluator has no evidence to score it. Stick to dimensions observable from code artifacts,
build output, test results, and benchmark measurements.
