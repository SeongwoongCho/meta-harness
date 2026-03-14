#!/usr/bin/env bash
# prompt-interceptor.sh — Reinforce meta-harness routing. Detect pending evaluations.

# Consume stdin
cat > /dev/null 2>&1 || true

# Check if there's a pending evaluation from a previous pipeline run
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
STATE_DIR="${PROJECT_ROOT}/.meta-harness"
SESSION_ID="${CLAUDE_SESSION_ID:-}"
if [ -z "$SESSION_ID" ]; then
  SID_FILE="${STATE_DIR}/.current-session-id"
  [ -f "$SID_FILE" ] && SESSION_ID=$(cat "$SID_FILE")
fi

EVAL_PENDING=""
if [ -n "$SESSION_ID" ]; then
  PENDING_FILE="${STATE_DIR}/sessions/${SESSION_ID}/.eval-pending"
  [ -f "$PENDING_FILE" ] && EVAL_PENDING="true"
fi

if [ "$EVAL_PENDING" = "true" ]; then
  cat <<'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "[meta-harness] WARNING: A harness execution completed but evaluation was NOT run. You MUST spawn the evaluator agent NOW (Step 5 of the pipeline) before handling this new user message. Read .meta-harness/sessions/ for evidence. After evaluation completes, remove .eval-pending and then handle the user's message."
  }
}
EOF
else
  cat <<'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "[meta-harness] Route this task through the meta-harness pipeline (using-meta-harness-default skill) before responding directly."
  }
}
EOF
fi

exit 0
