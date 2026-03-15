#!/usr/bin/env bash
# prompt-interceptor.sh — Reinforce adaptive-harness routing. Detect pending evaluations.
# Only injects routing reminders when pipeline mode is active (auto or run).

# Consume stdin
cat > /dev/null 2>&1 || true

# Check pipeline mode and pending evaluations
source "$(dirname "${BASH_SOURCE[0]:-$0}")/lib.sh"
PROJECT_ROOT="$(resolve_project_root)"
STATE_DIR="$(state_dir)"
SESSION_ID="${CLAUDE_SESSION_ID:-}"
if [ -z "$SESSION_ID" ]; then
  SID_FILE="${STATE_DIR}/.current-session-id"
  [ -f "$SID_FILE" ] && SESSION_ID=$(cat "$SID_FILE")
fi

# Read pipeline mode: "auto" | "run" | absent (= off)
PIPELINE_MODE=""
MODE_FILE="${STATE_DIR}/.pipeline-mode"
[ -f "$MODE_FILE" ] && PIPELINE_MODE=$(cat "$MODE_FILE" 2>/dev/null)

# Check for pending evaluation
EVAL_PENDING=""
if [ -n "$SESSION_ID" ]; then
  PENDING_FILE="${STATE_DIR}/sessions/${SESSION_ID}/.eval-pending"
  [ -f "$PENDING_FILE" ] && EVAL_PENDING="true"
fi

# Priority 1: Pending evaluation warning (always fires if eval pending, regardless of mode)
if [ "$EVAL_PENDING" = "true" ]; then
  cat <<'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "[adaptive-harness] WARNING: A harness execution completed but evaluation was NOT run. You MUST spawn the evaluator agent NOW (Step 5 of the pipeline) before handling this new user message. Read .adaptive-harness/sessions/ for evidence. After evaluation completes, remove .eval-pending and then handle the user's message."
  }
}
EOF

# Priority 2: Auto-mode active — reinforce routing
elif [ "$PIPELINE_MODE" = "auto" ]; then
  cat <<'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "[adaptive-harness] Route this task through the adaptive-harness pipeline (using-adaptive-harness skill) before responding directly."
  }
}
EOF

# Priority 3: One-shot run active — reinforce for current run only
elif [ "$PIPELINE_MODE" = "run" ]; then
  cat <<'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "[adaptive-harness] One-shot /adaptive-harness:run is active. Route this task through the pipeline. Pipeline mode will be cleared after completion."
  }
}
EOF

# Priority 4: No active mode — silent (no routing injection)
else
  cat <<'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": ""
  }
}
EOF
fi

exit 0
