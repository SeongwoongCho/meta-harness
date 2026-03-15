#!/usr/bin/env bash
# migrate.sh — Migrate .adaptive-harness project state when plugin version changes.
#
# Behaviors:
#   - Reads plugin version from ADAPTIVE_HARNESS_PLUGIN_VERSION env var or
#     ${PLUGIN_ROOT}/.claude-plugin/plugin.json
#   - Reads project version from .adaptive-harness/.plugin-version
#     (missing file treated as "0.0.0" → full migration)
#   - If versions match: exits 0, outputs {"status":"up_to_date"} JSON
#   - If ADAPTIVE_HARNESS_SKIP_MIGRATION=1: exits 0, skips all migration
#   - On mismatch: performs migration, outputs JSON summary of changes
#
# Migration steps:
#   1. Backup harness-pool.json → harness-pool.json.bak
#   2. Add new harnesses from plugin to pool (preserving existing weights)
#   3. Add missing config fields to config.yaml
#   4. Write updated .plugin-version
#
# Outputs valid JSON to stdout (summary or up_to_date status).
# Diagnostic messages go to stderr.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]:-$0}")/lib.sh"

PLUGIN_ROOT="$(resolve_plugin_root)"
PROJECT_ROOT="$(resolve_project_root)"
STATE_DIR="$(state_dir)"

# --- Escape hatch ---
if [ "${ADAPTIVE_HARNESS_SKIP_MIGRATION:-}" = "1" ]; then
  echo "[adaptive-harness migrate] Skipped (ADAPTIVE_HARNESS_SKIP_MIGRATION=1)" >&2
  printf '{"status":"skipped","reason":"ADAPTIVE_HARNESS_SKIP_MIGRATION=1"}\n'
  exit 0
fi

# --- Read plugin version ---
PLUGIN_JSON="${PLUGIN_ROOT}/.claude-plugin/plugin.json"
if [ -n "${ADAPTIVE_HARNESS_PLUGIN_VERSION:-}" ]; then
  PLUGIN_VERSION="${ADAPTIVE_HARNESS_PLUGIN_VERSION}"
elif [ -f "$PLUGIN_JSON" ]; then
  PLUGIN_VERSION=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('version','1.0.0'))" "$PLUGIN_JSON" 2>/dev/null || echo "1.0.0")
else
  PLUGIN_VERSION="1.0.0"
fi

# --- Read project version ---
VERSION_FILE="${STATE_DIR}/.plugin-version"
if [ -f "$VERSION_FILE" ]; then
  PROJECT_VERSION=$(cat "$VERSION_FILE" 2>/dev/null || echo "0.0.0")
else
  PROJECT_VERSION="0.0.0"
fi

echo "[adaptive-harness migrate] Plugin version: ${PLUGIN_VERSION}, Project version: ${PROJECT_VERSION}" >&2

# --- Check if migration needed ---
if [ "$PLUGIN_VERSION" = "$PROJECT_VERSION" ]; then
  echo "[adaptive-harness migrate] Up to date (${PLUGIN_VERSION})" >&2
  printf '{"status":"up_to_date","version":"%s"}\n' "$PLUGIN_VERSION"
  exit 0
fi

echo "[adaptive-harness migrate] Migration needed: ${PROJECT_VERSION} → ${PLUGIN_VERSION}" >&2

# --- Run migration via Python ---
POOL_FILE="${STATE_DIR}/harness-pool.json"
CONFIG_FILE="${STATE_DIR}/config.yaml"
HARNESS_DIR="${PLUGIN_ROOT}/harnesses"

python3 - "$STATE_DIR" "$POOL_FILE" "$CONFIG_FILE" "$HARNESS_DIR" "$PLUGIN_VERSION" "$PROJECT_VERSION" <<'MIGRATE_PY'
import json
import os
import shutil
import sys

state_dir, pool_file, config_file, harnesses_dir, plugin_version, project_version = sys.argv[1:]

skip_dirs = {"experimental", "archived", "__pycache__", "_shared"}

changes = {
    "from_version": project_version,
    "to_version": plugin_version,
    "harnesses_added": [],
    "config_fields_added": [],
}

# --- Step 1: Backup harness-pool.json ---
if os.path.isfile(pool_file):
    shutil.copy2(pool_file, pool_file + ".bak")
    print(f"[adaptive-harness migrate] Backed up harness-pool.json → harness-pool.json.bak", file=sys.stderr)

# --- Step 2: Add missing harnesses to pool ---
if os.path.isfile(pool_file):
    with open(pool_file) as fh:
        pool = json.load(fh)
else:
    pool = {"stable": {}, "experimental": {}, "last_updated": None, "last_merged_session": None}

if os.path.isdir(harnesses_dir):
    for name in sorted(os.listdir(harnesses_dir)):
        full = os.path.join(harnesses_dir, name)
        if os.path.isdir(full) and name not in skip_dirs and not name.startswith("."):
            if name not in pool.get("stable", {}) and name not in pool.get("experimental", {}):
                pool.setdefault("stable", {})[name] = {
                    "weight": 1.0,
                    "total_runs": 0,
                    "successes": 0,
                    "failures": 0,
                    "consecutive_successes": 0,
                }
                changes["harnesses_added"].append(name)
                print(f"[adaptive-harness migrate] Added harness to pool: {name}", file=sys.stderr)

with open(pool_file, "w") as fh:
    json.dump(pool, fh, indent=2)

# --- Step 3: Add missing config fields to config.yaml ---
if os.path.isfile(config_file):
    with open(config_file) as fh:
        config_text = fh.read()

    # Add missing 'evolution:' section if absent
    if "evolution:" not in config_text:
        config_text = config_text.rstrip() + "\n\nevolution:\n  enabled: true\n  promotion_threshold: 5\n  demotion_threshold: 5\n  target_pool: experimental\n"
        changes["config_fields_added"].append("evolution")

    # Add missing 'ensemble:' section if absent
    if "ensemble:" not in config_text:
        config_text = config_text.rstrip() + "\n\nensemble:\n  mode: auto\n"
        changes["config_fields_added"].append("ensemble")

    if changes["config_fields_added"]:
        # Backup config.yaml too
        shutil.copy2(config_file, config_file + ".bak")
        with open(config_file, "w") as fh:
            fh.write(config_text)
        print(f"[adaptive-harness migrate] Config fields added: {changes['config_fields_added']}", file=sys.stderr)

# --- Output JSON summary ---
summary = {
    "status": "migrated",
    "migrated": True,
    "from_version": project_version,
    "to_version": plugin_version,
    "harnesses_added": changes["harnesses_added"],
    "config_fields_added": changes["config_fields_added"],
}
print(json.dumps(summary))
MIGRATE_PY

# --- Step 4: Write updated .plugin-version ---
printf '%s' "$PLUGIN_VERSION" > "$VERSION_FILE"
echo "[adaptive-harness migrate] Wrote .plugin-version: ${PLUGIN_VERSION}" >&2

exit 0
