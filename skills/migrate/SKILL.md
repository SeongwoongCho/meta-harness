---
name: migrate
description: "Manually invoke the adaptive-harness migration to update a project's .adaptive-harness directory to the current plugin version. Adds missing harnesses, updates config schema, and reports what changed."
---

# adaptive-harness migrate

Run this skill whenever you need to manually migrate the project's `.adaptive-harness` state to match the current plugin version. Typically this is triggered automatically at session start, but you can also invoke it manually via `/adaptive-harness:migrate`.

## When to Use

- You updated the adaptive-harness plugin and want to apply migrations immediately
- The session-start hook reported a migration notice but you want a detailed report
- You suspect the project state is out of sync with the plugin version

## Steps

### 1. Locate the migrate script

The migration script is at `${PLUGIN_ROOT}/hooks/migrate.sh`. Discover `PLUGIN_ROOT` from `.adaptive-harness/.plugin-root` if set, or use the `CLAUDE_PLUGIN_ROOT` environment variable.

```bash
PLUGIN_ROOT=$(cat .adaptive-harness/.plugin-root 2>/dev/null || echo "${CLAUDE_PLUGIN_ROOT}")
```

### 2. Run migrate.sh

```bash
bash "${PLUGIN_ROOT}/hooks/migrate.sh"
```

This outputs a JSON summary to stdout. Capture it:

```bash
MIGRATE_OUTPUT=$(bash "${PLUGIN_ROOT}/hooks/migrate.sh")
```

### 3. Parse and report the JSON output

The JSON output has this structure:

```json
{
  "status": "migrated",
  "migrated": true,
  "from_version": "0.9.0",
  "to_version": "1.0.0",
  "harnesses_added": ["new-harness-name", "another-harness"],
  "config_fields_added": ["evolution", "ensemble"],
  "changes": { ... }
}
```

Or when already up to date:

```json
{
  "status": "up_to_date",
  "version": "1.0.0"
}
```

Or when migration was skipped:

```json
{
  "status": "skipped",
  "reason": "ADAPTIVE_HARNESS_SKIP_MIGRATION=1"
}
```

### 4. Report to the user

After running, report in a concise format:

```
adaptive-harness migration complete.

Version: 0.9.0 → 1.0.0
Harnesses added: new-harness-name, another-harness
Config fields added: evolution, ensemble
Backup: .adaptive-harness/harness-pool.json.bak
```

If already up to date, report:
```
adaptive-harness is already up to date (version 1.0.0). No migration needed.
```

## Escape Hatch

To skip migration entirely, set `ADAPTIVE_HARNESS_SKIP_MIGRATION=1` before running the skill:

```bash
ADAPTIVE_HARNESS_SKIP_MIGRATION=1 bash "${PLUGIN_ROOT}/hooks/migrate.sh"
```

## Notes

- Migration is **idempotent**: running it multiple times with the same versions produces the same result
- Existing harness weights and run history are **always preserved** during migration
- Backup files (`.bak`) are created before any modifications
- Config values set by the user (domain, ensemble mode, etc.) are **never overwritten**
