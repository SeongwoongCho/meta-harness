#!/usr/bin/env bash
# subagent-complete.sh — Record subagent completion and mark pipeline as pending evaluation.

# Consume stdin
HOOK_INPUT=$(cat 2>/dev/null || echo "")

source "$(dirname "$0")/lib.sh"
STATE_DIR="$(state_dir)"
SESSION_ID="$(resolve_session_id "$STATE_DIR")"

# Record completion and conditionally mark pipeline as needing evaluation
if [ -n "$SESSION_ID" ]; then
  SESSION_DIR="${STATE_DIR}/sessions/${SESSION_ID}"
  if [ -d "$SESSION_DIR" ]; then
    TIMESTAMP="$(timestamp_utc)"
    printf '{"timestamp":"%s","event":"subagent_stop"}\n' "$TIMESTAMP" >> "${SESSION_DIR}/subagent-events.jsonl" 2>/dev/null || true

    # Check if a chain is in progress — if so, skip .eval-pending
    # The orchestrator writes .chain-in-progress before starting a chain
    # and removes it when the chain completes.
    CHAIN_FILE="${STATE_DIR}/.chain-in-progress"
    if [ -f "$CHAIN_FILE" ]; then
      # Chain step completed — do NOT mark eval pending (eval runs after full chain)
      CHAIN_MSG="[adaptive-harness] Chain step completed. Continue executing the next chain step IMMEDIATELY. Do NOT respond to the user, do NOT run evaluation yet. Evaluation runs ONCE after the entire chain finishes."
    else
      # Non-chain subagent completed — mark eval pending as before
      printf '%s' "$TIMESTAMP" > "${SESSION_DIR}/.eval-pending" 2>/dev/null || true
      CHAIN_MSG="[adaptive-harness] Subagent completed. Pipeline state: EVALUATION PENDING. Continue to Step 5 (evaluate) immediately — do not respond to the user first."
    fi
  fi
fi

cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "SubagentStop",
    "additionalContext": "${CHAIN_MSG:-[adaptive-harness] Subagent completed. Pipeline state: EVALUATION PENDING. Continue to Step 5 (evaluate) immediately.}"
  }
}
EOF

exit 0
