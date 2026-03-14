#!/usr/bin/env bash
# session-start.sh — Inject using-meta-harness-default/SKILL.md as additionalContext.
# Run: chmod +x hooks/session-start.sh
set -euo pipefail

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
SKILL_FILE="${PLUGIN_ROOT}/skills/using-meta-harness-default/SKILL.md"
# Use git root if available, otherwise PWD
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
STATE_DIR="${PROJECT_ROOT}/.meta-harness"

# Generate a stable session ID for this session and write it for other hooks to use
SESSION_ID="${CLAUDE_SESSION_ID:-}"
if [ -z "$SESSION_ID" ]; then
  SESSION_ID="session-$(date +%s)-$$"
fi
mkdir -p "${STATE_DIR}"
printf '%s' "${SESSION_ID}" > "${STATE_DIR}/.current-session-id"

# Create per-session evidence directory
mkdir -p "${STATE_DIR}/sessions/${SESSION_ID}/evidence"

# Read SKILL.md content — exit cleanly if file not found
if [ ! -f "$SKILL_FILE" ]; then
  exit 0
fi

SKILL_CONTENT=$(cat "$SKILL_FILE")

# Escape content for JSON: backslashes, double quotes, newlines, tabs
ESCAPED=$(printf '%s' "$SKILL_CONTENT" \
  | sed 's/\\/\\\\/g' \
  | sed 's/"/\\"/g' \
  | sed ':a;N;$!ba;s/\n/\\n/g' \
  | sed 's/\t/\\t/g')

# Output valid hook JSON with additionalContext
printf '{"hookSpecificOutput":{"additionalContext":"%s"}}\n' "$ESCAPED"
