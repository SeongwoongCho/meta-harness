#!/usr/bin/env bash
# lib.sh — Shared initialization functions for meta-harness hooks.
# Source this at the top of each hook: source "$(dirname "$0")/lib.sh"

# Resolve plugin root directory
resolve_plugin_root() {
  echo "${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[1]:-$0}")/.." && pwd)}"
}

# Resolve project root (git root, or walk up looking for .meta-harness/, never plugin cache)
resolve_project_root() {
  local root
  root="$(git rev-parse --show-toplevel 2>/dev/null)" && { echo "$root"; return 0; }

  # Walk up from CWD looking for .meta-harness/ directory marker
  local dir="$PWD"
  while [ "$dir" != "/" ]; do
    if [ -d "${dir}/.meta-harness" ]; then
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

# Resolve session ID from environment or .current-session-id file
# Usage: resolve_session_id "$STATE_DIR"
resolve_session_id() {
  local state_dir="$1"
  local sid="${CLAUDE_SESSION_ID:-}"
  if [ -z "$sid" ]; then
    local sid_file="${state_dir}/.current-session-id"
    if [ -f "$sid_file" ]; then
      sid=$(cat "$sid_file")
    fi
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
  local sd="${project_root}/.meta-harness"
  local plugin_root="${CLAUDE_PLUGIN_ROOT:-}"
  if [ -n "$plugin_root" ] && [[ "$sd" == "$plugin_root"* ]]; then
    echo "[meta-harness] ERROR: state_dir resolved inside plugin cache: ${sd}" >&2
    return 1
  fi
  echo "$sd"
}
