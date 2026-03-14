#!/usr/bin/env bash
# session-start.sh — Inject using-meta-harness-default/SKILL.md as additionalContext.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]:-$0}")/lib.sh"
PLUGIN_ROOT="$(resolve_plugin_root)"
SKILL_FILE="${PLUGIN_ROOT}/skills/using-meta-harness-default/SKILL.md"
PROJECT_ROOT="$(resolve_project_root)"
STATE_DIR="$(state_dir)"

# Generate a stable session ID and create directories
SESSION_ID="${CLAUDE_SESSION_ID:-session-$(date +%s)-$$}"
mkdir -p "${STATE_DIR}/sessions/${SESSION_ID}/evidence" 2>/dev/null || true
printf '%s' "${SESSION_ID}" > "${STATE_DIR}/.current-session-id" 2>/dev/null || true

# Read SKILL.md — exit cleanly if not found
if [ ! -f "$SKILL_FILE" ]; then
  cat <<'FALLBACK'
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "[meta-harness] Plugin loaded but SKILL.md not found."
  }
}
FALLBACK
  exit 0
fi

SKILL_CONTENT=$(cat "$SKILL_FILE")

# Escape for JSON using bash parameter substitution (same pattern as superpowers)
escape_for_json() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\n'/\\n}"
    s="${s//$'\r'/\\r}"
    s="${s//$'\t'/\\t}"
    printf '%s' "$s"
}

ESCAPED=$(escape_for_json "$SKILL_CONTENT")

cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "${ESCAPED}"
  }
}
EOF

exit 0
