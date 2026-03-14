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
# These 8 dimensions are present in every protocol.
# You MUST include all 8. You may re-weight them to accommodate custom dimensions,
# but they must all be present with weight > 0.
#
# CONSTRAINT: sum of ALL universal_dimensions weights
#           + sum of ALL custom_dimensions weights = 1.0 exactly
#
universal_dimensions:
  - name: build_success
    weight: 0.15          # Default: 0.20. Reduced here to make room for custom dims.
    type: binary
    description: "Project builds without errors after the change"
    scoring_guide: "1.0 if build succeeds with zero errors. 0.0 if build fails.
                    0.5 if build succeeds with warnings that did not exist before."

  - name: test_pass_rate
    weight: 0.15
    type: percentage
    description: "Fraction of tests passing after the change"
    scoring_guide: "Score = (passing tests / total tests). If no tests exist,
                    score 0.5 as neutral (not penalized for pre-existing gap)."

  - name: code_quality
    weight: 0.10
    type: score_0_to_1
    description: "Static analysis, style conformance, and structural quality"
    scoring_guide: "Consider: lint warnings introduced (deduct), complexity increase
                    (deduct), code duplication (deduct), follows existing conventions
                    (add). Score 0.7 as baseline for clean but unremarkable code."

  - name: robustness
    weight: 0.10
    type: score_0_to_1
    description: "Edge case and error condition handling"
    scoring_guide: "Score based on: null/undefined guards present, error propagation
                    correct, boundary conditions handled. Deduct for each obvious
                    unhandled edge case."

  - name: maintainability
    weight: 0.05
    type: score_0_to_1
    description: "Readability, modularity, and ease of future modification"
    scoring_guide: "Consider: function length, naming clarity, comment quality,
                    single responsibility. Score 0.7 for acceptable maintainability."

  - name: security
    weight: 0.05
    type: score_0_to_1
    description: "No obvious security vulnerabilities introduced"
    scoring_guide: "Score 1.0 if no security concerns. Deduct for: SQL injection risk,
                    unvalidated input, exposed secrets, insecure defaults. Score 0.0
                    if a critical vulnerability is introduced."

  - name: readability
    weight: 0.05
    type: score_0_to_1
    description: "Code is clear, self-documenting, and easy to understand"
    scoring_guide: "Consider: variable naming, function naming, inline comments where
                    non-obvious logic exists. Score 0.7 as baseline for readable code."

  - name: error_handling
    weight: 0.05
    type: score_0_to_1
    description: "Errors are handled gracefully and informatively"
    scoring_guide: "Consider: error messages are descriptive, errors are not swallowed,
                    recovery paths exist where appropriate."

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
    - build_success               # These dimensions must individually score >= 0.5
    # - test_pass_rate            # Add dimensions that are non-negotiable

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

These 8 dimensions are present in every protocol with their default weights:

| Dimension | Default Weight | Type | What it measures |
|-----------|---------------|------|-----------------|
| `build_success` | 0.20 | binary | Does the project build? |
| `test_pass_rate` | 0.20 | percentage | What fraction of tests pass? |
| `code_quality` | 0.15 | score_0_to_1 | Static analysis and style |
| `robustness` | 0.10 | score_0_to_1 | Edge case handling |
| `maintainability` | 0.10 | score_0_to_1 | Readability and modularity |
| `security` | 0.10 | score_0_to_1 | No vulnerabilities introduced |
| `readability` | 0.10 | score_0_to_1 | Self-documenting code |
| `error_handling` | 0.05 | score_0_to_1 | Graceful error handling |

Default total: **1.00**

When you add custom dimensions, you must reduce universal dimension weights to maintain
the 1.0 sum. The typical approach is to reduce `build_success` and `test_pass_rate`
proportionally since they dominate the default weighting.

---

## Dimension Types

| Type | Range | Description | When to use |
|------|-------|-------------|-------------|
| `binary` | `0.0` or `1.0` | Pass/fail only | Go/no-go criteria (build passes, deployment succeeds) |
| `percentage` | `0.0` to `1.0` | Continuous 0%–100% | Coverage, test pass rate, benchmark scores |
| `score_0_to_1` | `0.0` to `1.0` | Evaluator judgment | Qualitative assessments (code quality, readability) |

---

## Weight Constraints

**The total of all dimension weights must sum exactly to 1.0.**

This constraint is validated at protocol load time. If the sum is not 1.0, the protocol
will fail to load.

**Recommended weight budget allocation:**

| Scenario | Build/Test | Custom dims | Notes |
|----------|-----------|-------------|-------|
| General purpose (no custom) | 0.40 (build+test) | 0 | Use `code-quality-standard` |
| One important custom dim | 0.30 | 0.30 | Halve build/test weight |
| Two important custom dims | 0.25 | 0.45 | Split build/test to 0.10 each |
| Three+ custom dims | 0.20 | 0.60 | Minimum build/test floor: 0.10 each |

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

### `code-quality-standard` — No custom dimensions

All 8 universal dimensions at default weights. Use as the baseline.
Best for: projects without strong domain-specific quality criteria.

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

### 3. Compare with `code-quality-standard`

Run the same task twice with different protocols and compare scores:

```
/meta-harness-run --protocol=code-quality-standard "your test task"
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
| `{aspect}-standard` | `code-quality-standard` | General-purpose baselines |
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
`error_handling` in the default protocol. The result is a protocol that measures
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
