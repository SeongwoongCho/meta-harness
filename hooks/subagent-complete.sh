#!/usr/bin/env bash
# subagent-complete.sh — Record subagent completion and remind orchestrator.

# Consume stdin
HOOK_INPUT=$(cat 2>/dev/null || echo "")

PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
STATE_DIR="${PROJECT_ROOT}/.meta-harness"

SESSION_ID="${CLAUDE_SESSION_ID:-}"
if [ -z "$SESSION_ID" ]; then
  SESSION_ID_FILE="${STATE_DIR}/.current-session-id"
  if [ -f "$SESSION_ID_FILE" ]; then
    SESSION_ID=$(cat "$SESSION_ID_FILE")
  fi
fi

# Record completion if session exists
if [ -n "$SESSION_ID" ]; then
  SESSION_DIR="${STATE_DIR}/sessions/${SESSION_ID}"
  if [ -d "$SESSION_DIR" ]; then
    TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
    printf '{"timestamp":"%s","event":"subagent_stop"}\n' "$TIMESTAMP" >> "${SESSION_DIR}/subagent-events.jsonl" 2>/dev/null || true
  fi
fi

cat <<'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "SubagentStop",
    "additionalContext": "[meta-harness] A subagent completed. If this was a harness execution subagent, check the results and trigger evaluation via the evaluator agent. Evidence is in .meta-harness/sessions/"
  }
}
EOF

exit 0
