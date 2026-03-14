#!/usr/bin/env bash
# lib.sh — Shared initialization functions for meta-harness hooks.
# Source this at the top of each hook: source "$(dirname "$0")/lib.sh"

# Resolve plugin root directory
resolve_plugin_root() {
  echo "${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[1]:-$0}")/.." && pwd)}"
}

# Resolve project root (git root or PWD)
resolve_project_root() {
  git rev-parse --show-toplevel 2>/dev/null || pwd
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

# Standard state directory
state_dir() {
  echo "$(resolve_project_root)/.meta-harness"
}
