#!/usr/bin/env bash
# subagent-complete.sh — Record subagent completion and remind orchestrator to evaluate.
# Fires on SubagentStop for all subagents.
# Run: chmod +x hooks/subagent-complete.sh
set -euo pipefail

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
STATE_DIR="${PLUGIN_ROOT}/state"

# Resolve session ID
SESSION_ID="${CLAUDE_SESSION_ID:-}"
if [ -z "$SESSION_ID" ]; then
  SESSION_ID_FILE="${STATE_DIR}/.current-session-id"
  if [ -f "$SESSION_ID_FILE" ]; then
    SESSION_ID=$(cat "$SESSION_ID_FILE")
  fi
fi

# Read hook input (subagent metadata from stdin)
HOOK_INPUT=$(cat)

TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)

# Record subagent completion event if session is tracked
if [ -n "$SESSION_ID" ]; then
  SESSION_DIR="${STATE_DIR}/sessions/${SESSION_ID}"
  mkdir -p "$SESSION_DIR"

  ESCAPED_INPUT=$(printf '%s' "$HOOK_INPUT" \
    | sed 's/\\/\\\\/g' \
    | sed 's/"/\\"/g' \
    | sed ':a;N;$!ba;s/\n/\\n/g' \
    | sed 's/\t/\\t/g')

  TMP_FILE="${SESSION_DIR}/subagent-${TIMESTAMP}.json.tmp"
  cat > "$TMP_FILE" <<EOF
{
  "timestamp": "${TIMESTAMP}",
  "session_id": "${SESSION_ID}",
  "event": "subagent_stop",
  "hook_input": "${ESCAPED_INPUT}"
}
EOF
  mv "$TMP_FILE" "${SESSION_DIR}/subagent-${TIMESTAMP}.json"
fi

# Output additionalContext reminding the orchestrator to check for harness completion
REMINDER="[meta-harness] A subagent just completed. If this was a harness subagent executing a task, follow the using-meta-harness-default skill: read evidence from state/sessions/${SESSION_ID}/evidence/, spawn the evaluator agent, and record the evaluation result."

printf '{"hookSpecificOutput":{"additionalContext":"%s"}}\n' "$REMINDER"
