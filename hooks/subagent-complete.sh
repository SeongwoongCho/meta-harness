#!/usr/bin/env bash
# subagent-complete.sh — Record subagent completion and mark pipeline as pending evaluation.

# Consume stdin
HOOK_INPUT=$(cat 2>/dev/null || echo "")

source "$(dirname "${BASH_SOURCE[0]:-$0}")/lib.sh"
PLUGIN_ROOT="$(resolve_plugin_root)"
STATE_DIR="$(state_dir)"

# Auto-initialize if state dir is missing or broken; abort silently on failure
if [ -z "$STATE_DIR" ] || [ ! -d "$STATE_DIR" ]; then
  ensure_state_dir "$STATE_DIR" "$PLUGIN_ROOT" 2>/dev/null || exit 0
fi

SESSION_ID="$(resolve_session_id "$STATE_DIR")"

# Initialize CHAIN_MSG to avoid uninitialized variable issues (M1 fix)
CHAIN_MSG=""

# Check if a chain is in progress — must happen OUTSIDE the session dir block
# so it fires even when SESSION_DIR doesn't exist (C2 fix).
# The orchestrator writes .chain-in-progress before starting a chain
# and removes it when the chain completes.
CHAIN_FILE="${STATE_DIR}/.chain-in-progress"
if [ -f "$CHAIN_FILE" ]; then
  # Chain step completed — do NOT mark eval pending (eval runs after full chain)
  CHAIN_MSG="[adaptive-harness] Chain step completed. Continue executing the next chain step IMMEDIATELY. Do NOT respond to the user, do NOT run evaluation yet. Evaluation runs ONCE after the entire chain finishes."
fi

# Record completion and conditionally mark pipeline as needing evaluation
if [ -n "$SESSION_ID" ]; then
  SESSION_DIR="${STATE_DIR}/sessions/${SESSION_ID}"
  if [ -d "$SESSION_DIR" ]; then
    TIMESTAMP="$(timestamp_utc)"
    printf '{"timestamp":"%s","event":"subagent_stop"}\n' "$TIMESTAMP" >> "${SESSION_DIR}/subagent-events.jsonl" 2>/dev/null || true

    if [ -z "$CHAIN_MSG" ]; then
      # Non-chain subagent completed — mark eval pending as before
      printf '%s' "$TIMESTAMP" > "${SESSION_DIR}/.eval-pending" 2>/dev/null || true
    fi
  fi
fi

# M2 fix: Apply escape_for_json to CHAIN_MSG before JSON interpolation
# to prevent JSON injection from special characters (quotes, backslashes, newlines).
DEFAULT_MSG="[adaptive-harness] Subagent completed. Pipeline state: EVALUATION PENDING. Continue to Step 5 (evaluate) immediately — do not respond to the user first."
SAFE_MSG=$(escape_for_json "${CHAIN_MSG:-${DEFAULT_MSG}}")

cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "SubagentStop",
    "additionalContext": "${SAFE_MSG}"
  }
}
EOF

exit 0
