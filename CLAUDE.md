# adaptive-harness — Project Instructions for AI Agents

## Git Workflow

This project follows a structured branching strategy. **All AI agents must follow these rules without exception.**

### Branch Structure

| Branch | Purpose |
|--------|---------|
| `main` | Stable releases only. Contains tagged versions. |
| `dev` | Integration branch. All feature work is merged here first. |
| `feat/*`, `fix/*`, `docs/*`, `harness/*`, `fixture/*`, `chore/*` | Short-lived feature branches. Always branched from `dev`. |

### Rules for AI Agents

1. **Never commit directly to `main` or `dev`.**
2. **Always create a new feature branch from `dev` before making any changes.**
   ```
   git checkout dev
   git pull origin dev
   git checkout -b feat/<short-description>
   ```
3. **All pull requests must target `dev`**, not `main`.
4. **Branch naming convention:** Use one of the following prefixes:
   - `feat/` — new feature or capability
   - `fix/` — bug fix
   - `docs/` — documentation only
   - `harness/` — harness definition changes
   - `fixture/` — fixture or test data changes
   - `chore/` — maintenance, version bumps, tooling

### Release Flow

When a version is ready to release:
1. Merge `dev` into `main` via a PR.
2. Tag the merge commit on `main` with the version: `vX.Y.Z` (semver).
3. Push the tag: `git push origin vX.Y.Z`.

### Version Files

When bumping the project version, update **both** files:
- `.claude-plugin/plugin.json` — `"version"` field
- `.claude-plugin/marketplace.json` — `"version"` field (appears twice: once in `plugins[0]` and once at the root)

### Current Version

**1.0.1**
