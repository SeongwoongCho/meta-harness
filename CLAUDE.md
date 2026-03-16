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

#### Automated Release (recommended)

Use the **prepare-release** workflow to automate version bumping and PR creation:

1. Go to **Actions → Prepare Release → Run workflow** on GitHub.
2. Enter the new version (e.g. `1.2.0`) and click **Run workflow**.
3. The workflow will:
   - Run `scripts/bump_version.py <version>` to update all version files.
   - Commit the version bump to `dev`.
   - Open a PR from `dev` → `main` with auto-generated release notes.
4. Review and merge the PR.
5. Tag the merge commit: `git tag v1.2.0 && git push origin v1.2.0`.
6. The **release** workflow runs automatically on tag push, validates the version, generates the changelog, and creates a GitHub Release.

#### Manual Release

When a version is ready to release manually:
1. Bump all version files in one command:
   ```
   python3 scripts/bump_version.py <new_version>
   ```
2. Commit, push, and open a PR from `dev` → `main`.
3. Merge the PR, then tag the merge commit on `main`:
   ```
   git tag v<new_version>
   git push origin v<new_version>
   ```

#### Release Scripts

| Script | Purpose |
|--------|---------|
| `scripts/bump_version.py <version>` | Update version in `plugin.json`, `marketplace.json`, and `CLAUDE.md` |
| `scripts/generate_changelog.py [FROM_TAG] [TO_REF]` | Generate markdown changelog from git log |

#### GitHub Actions Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `.github/workflows/release.yml` | `git push origin vX.Y.Z` | Validates version, generates changelog, creates GitHub Release |
| `.github/workflows/prepare-release.yml` | `workflow_dispatch` | Bumps version, commits to `dev`, opens PR to `main` |
| `.github/workflows/test.yml` | Push/PR to `main` | Runs full test suite |

### Version Files

When bumping the project version, all three locations must be in sync (use `scripts/bump_version.py` to update them atomically):
- `.claude-plugin/plugin.json` — `"version"` field
- `.claude-plugin/marketplace.json` — `"version"` field (appears twice: once in `plugins[0]` and once at the root)
- `CLAUDE.md` — bold version on the **Current Version** line

### Current Version

**1.0.4**
