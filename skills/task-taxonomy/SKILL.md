---
name: task-taxonomy
description: "Reference for the 6-axis task taxonomy used by adaptive-harness routing. Use when user asks how tasks are classified."
---

# Task Taxonomy Reference

## Purpose

Adaptive-harness classifies every incoming task on 6 independent axes before routing to a harness. This taxonomy drives the routing decision and ensemble trigger logic. The router agent (LLM-based) reasons over the task description and codebase context to assign values — it does not use keyword heuristics.

---

## The 6 Axes

### Axis 1: task_type

What category of work does this task represent?

| Value | Description | Example tasks |
|-------|-------------|---------------|
| `bugfix` | Fix a defect in existing behavior | "Login fails when email has uppercase letters" |
| `feature` | Add new functionality | "Add dark mode support" |
| `refactor` | Restructure code without changing behavior | "Extract the auth logic into a separate module" |
| `research` | Investigate, experiment, or benchmark | "Compare three approaches to rate limiting" |
| `migration` | Upgrade dependencies or migrate between systems | "Migrate from Express 4 to Fastify" |
| `benchmark` | Measure and analyze performance | "Profile the query execution and find bottlenecks" |
| `incident` | Urgent production issue requiring fast response | "API returning 500s in production right now" |
| `greenfield` | Build a multi-component system from scratch | "Build a FastAPI backend with webhooks, InfluxDB, and Grafana dashboard" |

### Axis 2: uncertainty

How well-defined is the solution before implementation begins?

| Value | Description | Signs |
|-------|-------------|-------|
| `low` | Clear solution path; solution is known before starting | Spec exists, existing pattern to follow, fix is obvious |
| `medium` | Solution approach is known but details require exploration | Roughly know what to do, some unknowns in implementation |
| `high` | Solution path is unclear; multiple approaches plausible | Novel problem, no precedent, multiple competing designs |

### Axis 3: blast_radius

How much of the codebase could be affected by this change?

| Value | Description | Signs |
|-------|-------------|-------|
| `local` | Change confined to 1-3 files; no cross-cutting concerns | Single function fix, isolated module addition |
| `cross-module` | Change touches multiple modules or shared interfaces | Modifying a shared utility, changing an API contract |
| `repo-wide` | Change affects the entire codebase or public interfaces | Renaming a core abstraction, changing the data model, upgrading a pervasive dependency |

### Axis 4: verifiability

How easily can success be confirmed after implementation?

| Value | Description | Signs |
|-------|-------------|-------|
| `easy` | Automated tests clearly pass/fail; behavior is deterministic | Unit tests exist, CI passes, output is binary correct/incorrect |
| `moderate` | Tests exist but don't fully capture correctness; human review needed | Integration tests cover most but not all cases; requires spot-checking |
| `hard` | No automated verification; correctness requires deep reasoning or human judgment | Research results, UX quality, architectural soundness, ML model accuracy |

### Axis 5: latency_sensitivity

How time-sensitive is task completion?

| Value | Description | Signs |
|-------|-------------|-------|
| `low` | Quality over speed; thoroughness preferred | Refactoring, migration planning, research, standard development |
| `high` | Fast response critical; speed over comprehensiveness | Production incidents, demo blockers, urgent hotfixes |

### Axis 6: domain

What technical domain does this task primarily involve?

| Value | Description | Separated from |
|-------|-------------|----------------|
| `backend` | Server-side code, APIs, databases, services | — |
| `frontend` | UI, browser code, CSS, accessibility | — |
| `mobile` | Native mobile apps (iOS, Android, React Native, Flutter) | `frontend` |
| `ml-research` | Machine learning, model training, data pipelines, research | — |
| `data-engineering` | ETL pipelines, data warehousing, Spark, Airflow, dbt | `ml-research` |
| `devops` | CI/CD pipelines, deployment automation, observability | `infra` |
| `security` | Vulnerability audits, auth hardening, compliance | `backend` + `infra` |
| `infra` | Infrastructure provisioning, cloud configuration, networking | — |
| `docs` | Documentation, README, API docs, comments | — |

An optional `domain_hint` free-text field may accompany `domain` to give extra context for mixed-domain or niche tasks (e.g., `"also touches devops"`, `"Spark ETL pipeline"`, `"Kubernetes operator"`). This field is for logging and analytics only — it does not affect routing.

---

## How Taxonomy Feeds Routing

The router agent uses these 6 axes to match against harness trigger conditions defined in each `contract.yaml`. Example trigger conditions:

```yaml
# tdd-driven/contract.yaml
trigger:
  task_types: [bugfix, feature]
  uncertainty: [low, medium]
  verifiability: [easy, moderate]

# research-iteration/contract.yaml
trigger:
  task_types: [research, benchmark]
  uncertainty: [high]

# migration-safe/contract.yaml
trigger:
  task_types: [migration]
  blast_radius: [repo-wide]
```

When multiple harnesses match, the router uses historical weights from `.adaptive-harness/harness-pool.json` to break ties, preferring higher-weight harnesses.

---

## Ensemble Trigger Condition

Canonical rule is defined in `agents/router.md` (`<ensemble_rule>`):
`ensemble_required = (uncertainty == "high") AND (verifiability == "hard" OR blast_radius == "repo-wide")`

---

## Fast-Path Condition

The router outputs `skip_routing: true` for **zero-work acknowledgments** that require no code changes, no analysis, and no file modifications:

- Acknowledgments or meta-conversation ("ok", "sounds good", "thanks", "got it")
- Pure clarification questions ("what does X mean?")

The following are NOT fast-path (they require actual work):
- "fix that typo" -- requires a code change
- "add a newline" -- requires a file edit
- "refactor this" -- requires analysis + code changes

---

## Classification Examples

| Task description | task_type | uncertainty | blast_radius | verifiability | latency_sensitivity | domain |
|-----------------|-----------|-------------|--------------|---------------|--------------------|----|
| "Login fails when email has uppercase" | bugfix | low | local | easy | low | backend |
| "Add dark mode to the settings page" | feature | medium | local | moderate | low | frontend |
| "Migrate from Webpack 4 to Vite" | migration | high | repo-wide | moderate | low | frontend |
| "Compare Redis vs Memcached for our cache layer" | research | high | local | hard | low | infra |
| "API is throwing 500s in production" | incident | low | local | easy | high | backend |
| "Extract shared auth logic used in 12 modules" | refactor | medium | cross-module | moderate | low | backend |
| "Add deep link handling to React Native app" | feature | medium | local | moderate | low | mobile |
| "Build Spark ETL pipeline for order aggregation" | feature | medium | local | moderate | low | data-engineering |
| "Add canary deployment stage to CI/CD pipeline" | feature | medium | cross-module | moderate | low | devops |
| "Audit and harden JWT authentication" | refactor | medium | cross-module | moderate | low | security |
| "Build a FastAPI backend with GitHub webhooks, InfluxDB storage, and Grafana dashboards" | greenfield | high | repo-wide | moderate | low | backend |
| "Create a microservice that processes images, stores in S3, and serves via CDN" | greenfield | high | repo-wide | moderate | low | infra |

---

## Usage Notes

- The router agent assigns taxonomy values using LLM reasoning — it reads the task description, considers codebase context, and classifies holistically.
- Classification is logged in every `eval-{timestamp}.json` for retrospective analysis and router accuracy improvement.
- If you believe the router misclassified your task, use `/adaptive-harness:run --harness=name` to override the selection.
