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

# --- Repair missing core files before running migration ---
POOL_FILE="${STATE_DIR}/harness-pool.json"
CONFIG_FILE="${STATE_DIR}/config.yaml"
HARNESS_DIR="${PLUGIN_ROOT}/harnesses"

# If config.yaml is missing, write --general defaults before migrating (H5 fix)
if [ ! -f "$CONFIG_FILE" ]; then
  echo "[adaptive-harness migrate] config.yaml missing — bootstrapping with --general defaults" >&2
  python3 - "${CONFIG_FILE}" <<'MIGRATE_CONFIG_EOF'
import sys, datetime
path = sys.argv[1]
ts = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
content = f"""# adaptive-harness project configuration
# Auto-initialized with --general defaults during migration
version: "1.0"
generated_at: "{ts}"

project:
  domain: "general"

evaluation:
  primary_metrics:
    - correctness
    - completeness
    - quality

ensemble:
  mode: auto

evolution:
  enabled: true
  promotion_threshold: 5
  demotion_threshold: 5
  target_pool: "experimental"
"""
with open(path, 'w') as f:
    f.write(content)
MIGRATE_CONFIG_EOF
fi

# If harness-pool.json is missing, bootstrap it from scratch before migrating
# Uses atomic write pattern: write to .tmp then mv to final (C2 fix)
if [ ! -f "$POOL_FILE" ] && [ -d "$HARNESS_DIR" ]; then
  echo "[adaptive-harness migrate] harness-pool.json missing — bootstrapping from harnesses directory" >&2
  python3 - "$HARNESS_DIR" "$POOL_FILE" <<'MIGRATE_POOL_EOF'
import json, sys, os
harnesses_dir, pool_file = sys.argv[1], sys.argv[2]
pool = {"stable": {}, "experimental": {}, "last_updated": None, "last_merged_session": None}
skip = {"experimental", "archived", "__pycache__", "_shared"}
for name in sorted(os.listdir(harnesses_dir)):
    full = os.path.join(harnesses_dir, name)
    if os.path.isdir(full) and name not in skip and not name.startswith("."):
        pool["stable"][name] = {
            "weight": 1.0, "total_runs": 0, "successes": 0,
            "failures": 0, "consecutive_successes": 0
        }
tmp_file = pool_file + ".tmp"
with open(tmp_file, 'w') as f:
    json.dump(pool, f, indent=2)
os.rename(tmp_file, pool_file)
print(f"[adaptive-harness migrate] Bootstrapped harness-pool.json with {len(pool['stable'])} harnesses.", file=sys.stderr)
MIGRATE_POOL_EOF
fi

# --- Run migration via Python ---

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

# --- Step 2b: Reclassify harnesses whose pool tier has changed ---
# If a harness is in experimental but its contract.yaml now says pool=stable
# (or vice versa), move it to the correct tier while preserving its stats.
reclassified = []
if os.path.isdir(harnesses_dir):
    for name in sorted(os.listdir(harnesses_dir)):
        full = os.path.join(harnesses_dir, name)
        if not os.path.isdir(full) or name in skip_dirs or name.startswith("."):
            continue
        contract_path = os.path.join(full, "contract.yaml")
        if not os.path.isfile(contract_path):
            continue
        try:
            import yaml
            with open(contract_path) as fh:
                contract = yaml.safe_load(fh)
            desired_tier = contract.get("pool", "stable")
        except Exception:
            continue
        # Check if harness is in the wrong tier
        wrong_tier = "experimental" if desired_tier == "stable" else "stable"
        if name in pool.get(wrong_tier, {}):
            entry = pool[wrong_tier].pop(name)
            pool.setdefault(desired_tier, {})[name] = entry
            reclassified.append(name)
            print(
                f"[adaptive-harness migrate] Reclassified {name}: {wrong_tier} → {desired_tier}",
                file=sys.stderr,
            )

if reclassified:
    with open(pool_file, "w") as fh:
        json.dump(pool, fh, indent=2)
    changes["harnesses_reclassified"] = reclassified

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
    "harnesses_reclassified": changes.get("harnesses_reclassified", []),
}
print(json.dumps(summary))
MIGRATE_PY

# --- Step 4: Write updated .plugin-version ---
printf '%s' "$PLUGIN_VERSION" > "$VERSION_FILE"
echo "[adaptive-harness migrate] Wrote .plugin-version: ${PLUGIN_VERSION}" >&2

exit 0
