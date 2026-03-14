#!/usr/bin/env bash
# prompt-interceptor.sh — Reinforce meta-harness routing on every user message.

# Consume stdin
cat > /dev/null 2>&1 || true

cat <<'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "[meta-harness] Follow the using-meta-harness-default skill: classify this task via the router agent and route it through the meta-harness pipeline before responding directly."
  }
}
EOF

exit 0
