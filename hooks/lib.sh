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
