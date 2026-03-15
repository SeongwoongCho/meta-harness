#!/usr/bin/env bash
# subagent-complete.sh — Record subagent completion and mark pipeline as pending evaluation.

# Consume stdin
HOOK_INPUT=$(cat 2>/dev/null || echo "")

source "$(dirname "$0")/lib.sh"
STATE_DIR="$(state_dir)"
SESSION_ID="$(resolve_session_id "$STATE_DIR")"

# Record completion and mark pipeline as needing evaluation
if [ -n "$SESSION_ID" ]; then
  SESSION_DIR="${STATE_DIR}/sessions/${SESSION_ID}"
  if [ -d "$SESSION_DIR" ]; then
    TIMESTAMP="$(timestamp_utc)"
    printf '{"timestamp":"%s","event":"subagent_stop"}\n' "$TIMESTAMP" >> "${SESSION_DIR}/subagent-events.jsonl" 2>/dev/null || true
    # Mark that evaluation is pending — prompt-interceptor reads this
    printf '%s' "$TIMESTAMP" > "${SESSION_DIR}/.eval-pending" 2>/dev/null || true
  fi
fi

cat <<'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "SubagentStop",
    "additionalContext": "[adaptive-harness] Subagent completed. Pipeline state: EVALUATION PENDING. Continue to Step 5 (evaluate) immediately — do not respond to the user first."
  }
}
EOF

exit 0
