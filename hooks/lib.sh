#!/usr/bin/env bash
# lib.sh — Shared initialization functions for adaptive-harness hooks.
# Source this at the top of each hook: source "$(dirname "$0")/lib.sh"

# Resolve plugin root directory
resolve_plugin_root() {
  echo "${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[1]:-$0}")/.." && pwd)}"
}

# Resolve project root (git root, or walk up looking for .adaptive-harness/, never plugin cache)
resolve_project_root() {
  local root
  root="$(git rev-parse --show-toplevel 2>/dev/null)" && { echo "$root"; return 0; }

  # Walk up from CWD looking for .adaptive-harness/ directory marker
  local dir="$PWD"
  while [ "$dir" != "/" ]; do
    if [ -d "${dir}/.adaptive-harness" ]; then
      echo "$dir"
      return 0
    fi
    dir="$(dirname "$dir")"
  done

  # Fallback to PWD, but never return a path inside the plugin cache
  local fallback="$PWD"
  local plugin_root="${CLAUDE_PLUGIN_ROOT:-}"
  if [ -n "$plugin_root" ] && [[ "$fallback" == "$plugin_root"* ]]; then
    echo "${HOME}" # Safe fallback — caller should detect and warn
    return 1
  fi
  echo "$fallback"
}

# Resolve session ID from .current-session-id file or environment variable.
# .current-session-id is preferred because it is written at session-start with
# the exact ID used to create the session directory. CLAUDE_SESSION_ID (Claude's
# UUID) is only used as a fallback when the file is absent.
# Usage: resolve_session_id "$STATE_DIR"
resolve_session_id() {
  local state_dir="$1"
  local sid=""
  local sid_file="${state_dir}/.current-session-id"
  if [ -f "$sid_file" ]; then
    sid=$(cat "$sid_file")
  fi
  if [ -z "$sid" ]; then
    sid="${CLAUDE_SESSION_ID:-}"
  fi
  echo "$sid"
}

# Generate ISO 8601 UTC timestamp
timestamp_utc() {
  date -u +%Y%m%dT%H%M%SZ
}

# Standard state directory (validated: never inside plugin cache)
state_dir() {
  local project_root
  project_root="$(resolve_project_root)"
  local sd="${project_root}/.adaptive-harness"
  local plugin_root="${CLAUDE_PLUGIN_ROOT:-}"
  if [ -n "$plugin_root" ] && [[ "$sd" == "$plugin_root"* ]]; then
    echo "[adaptive-harness] ERROR: state_dir resolved inside plugin cache: ${sd}" >&2
    return 1
  fi
  echo "$sd"
}

# ensure_state_dir — create or repair the .adaptive-harness state directory.
# Idempotent: if all required files exist, returns immediately (fast path).
# Usage: ensure_state_dir "$STATE_DIR" "$PLUGIN_ROOT"
# Returns 0 on success, 1 on failure (error message on stderr).
ensure_state_dir() {
  local sd="$1"
  local plugin_root="${2:-$(resolve_plugin_root)}"

  # Guard: empty or unset state dir path would cause writes to cwd (C1 fix)
  if [ -z "$sd" ]; then
    echo "[adaptive-harness] ERROR: ensure_state_dir: STATE_DIR is empty" >&2
    return 1
  fi

  # Fast path: all required files already exist
  if [ -f "${sd}/config.yaml" ] && [ -f "${sd}/harness-pool.json" ] && \
     [ -f "${sd}/.plugin-version" ] && [ -f "${sd}/.plugin-root" ]; then
    return 0
  fi

  # Create subdirectories
  mkdir -p "${sd}/sessions" "${sd}/evaluation-logs" "${sd}/evolution-proposals" \
    "${sd}/harnesses/experimental" "${sd}/harnesses/stable" 2>/dev/null || {
    echo "[adaptive-harness] ERROR: ensure_state_dir: cannot create directories under ${sd}" >&2
    return 1
  }

  # Write config.yaml with --general defaults (only if missing)
  if [ ! -f "${sd}/config.yaml" ]; then
    python3 - "${sd}/config.yaml" <<'CONFIG_EOF'
import sys, datetime
path = sys.argv[1]
ts = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
content = f"""# adaptive-harness project configuration
# Auto-initialized with --general defaults
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
CONFIG_EOF
    if [ $? -ne 0 ]; then
      echo "[adaptive-harness] ERROR: ensure_state_dir: failed to write config.yaml" >&2
      return 1
    fi
  fi

  # Bootstrap harness-pool.json from plugin harnesses/ directory (only if missing)
  # Uses atomic write pattern: write to .tmp then mv to final (C2 fix)
  if [ ! -f "${sd}/harness-pool.json" ]; then
    local harness_dir="${plugin_root}/harnesses"
    if [ ! -d "$harness_dir" ]; then
      echo "[adaptive-harness] ERROR: ensure_state_dir: harnesses directory not found: ${harness_dir}" >&2
      return 1
    fi
    python3 - "$harness_dir" "${sd}/harness-pool.json" <<'POOL_EOF'
import json, sys, os
harnesses_dir, pool_file = sys.argv[1], sys.argv[2]
pool = {"stable": {}, "experimental": {}, "last_updated": None, "last_merged_session": None}
skip = {"experimental", "archived", "__pycache__", "_shared"}
for name in sorted(os.listdir(harnesses_dir)):
    full = os.path.join(harnesses_dir, name)
    if os.path.isdir(full) and name not in skip and not name.startswith("."):
        pool["stable"][name] = {
            "weight": 1.0,
            "total_runs": 0,
            "successes": 0,
            "failures": 0,
            "consecutive_successes": 0
        }
tmp_file = pool_file + ".tmp"
with open(tmp_file, 'w') as f:
    json.dump(pool, f, indent=2)
os.rename(tmp_file, pool_file)
print(f"[adaptive-harness] ensure_state_dir: bootstrapped harness-pool.json with {len(pool['stable'])} harnesses.", file=sys.stderr)
POOL_EOF
    if [ $? -ne 0 ]; then
      echo "[adaptive-harness] ERROR: ensure_state_dir: failed to bootstrap harness-pool.json" >&2
      return 1
    fi
  fi

  # Write .plugin-version (only if missing)
  if [ ! -f "${sd}/.plugin-version" ]; then
    local plugin_json="${plugin_root}/.claude-plugin/plugin.json"
    local version
    if [ -f "$plugin_json" ]; then
      version=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('version','1.0.0'))" "$plugin_json" 2>/dev/null || echo "1.0.0")
    else
      version="${ADAPTIVE_HARNESS_PLUGIN_VERSION:-1.0.0}"
    fi
    printf '%s' "$version" > "${sd}/.plugin-version" 2>/dev/null || {
      echo "[adaptive-harness] ERROR: ensure_state_dir: cannot write .plugin-version" >&2
      return 1
    }
  fi

  # Write .plugin-root (only if missing)
  if [ ! -f "${sd}/.plugin-root" ]; then
    printf '%s' "$plugin_root" > "${sd}/.plugin-root" 2>/dev/null || {
      echo "[adaptive-harness] ERROR: ensure_state_dir: cannot write .plugin-root" >&2
      return 1
    }
  fi

  return 0
}

# escape_for_json — Escape a string for safe embedding in a JSON string value.
# Handles backslashes, double-quotes, newlines, carriage returns, and tabs.
# Usage: escaped=$(escape_for_json "$variable")
escape_for_json() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\n'/\\n}"
    s="${s//$'\r'/\\r}"
    s="${s//$'\t'/\\t}"
    printf '%s' "$s"
}
