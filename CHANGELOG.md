# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Features
- Add 5 new harnesses: deep-interview, simple-executor, documentation-writer, security-audit, performance-optimization
- Register all 5 new harnesses in the stable pool with weight=1.0
- Update router harness table and chaining guidelines for new harnesses
- Add README documentation for new harnesses

### Chores
- Add release automation scripts and GitHub Actions workflows

## [1.0.1] - 2026-03-15

### Features
- Add migrate skill with auto-migration on session start
- Add 5 harnesses adapted from gstack skills
- Add comprehensive test suite covering all adaptive-harness features
- Add pipeline mode state to prevent auto-routing after one-shot runs
- Instantiate all 14 workflow patterns as harnesses
- Add evolution system with workflow pattern library
- Add dynamic chain hints, OWASP review, task-aware evaluation
- Implement self-driving evaluation pipeline
- Add harness composability and general-capable harnesses
- Add `--general` flag to `/meta-harness:init` for quick setup

### Fixes
- Apply code review fixes for migrate skill
- Enforce mandatory router-first rule to prevent pipeline bypass
- Harden session ID resolution, idempotent proposals, and session-end guard
- Add pyyaml to CI deps for contract validation tests
- Replace hardcoded paths with dynamic resolution for CI compatibility
- Clarify router ensemble rule and eval logging
- Align session-end weight merge with actual weights.json format
- Close all 6 evaluation skip paths in the pipeline
- Harden hook scripts and add hookEventName

### Documentation
- Update built-in harness descriptions to match agent definitions
- Condense README with protocols and model routing
- Update README with installation and acknowledgments

### Refactors
- Rename meta-harness to adaptive-harness across entire project
- Unify command syntax, fix session-end stats merging, and harden evidence collection
- Overhaul meta-harness pipeline defaults, evolve tracking, and evaluation
- Adopt 6-axis universal evaluation model
- Separate agent personas and adopt task-agnostic dimensions
- Consolidate duplicated content across harnesses, hooks, and agents
- Register harness agents via symlinks

### Chores
- Bump version to 1.0.1 and add git workflow rules to CLAUDE.md
- Add `__pycache__` to `.gitignore` and remove cached files
- Add GitHub Actions workflow to run pytest on push and PR to main

## [1.0.0] - Initial Release

- Initial implementation of meta-harness v1.0

[Unreleased]: https://github.com/SeongwoongCho/adaptive-harness/compare/v1.0.1...HEAD
[1.0.1]: https://github.com/SeongwoongCho/adaptive-harness/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/SeongwoongCho/adaptive-harness/releases/tag/v1.0.0
