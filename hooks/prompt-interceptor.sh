#!/usr/bin/env bash
# prompt-interceptor.sh — Reinforce meta-harness routing on every user message.
# Output must be under 500 bytes.

# Consume stdin to prevent broken pipe errors
cat > /dev/null 2>&1 || true

REMINDER='[meta-harness] Follow the using-meta-harness-default skill: classify this task via the router agent and route it through the meta-harness pipeline before responding directly.'

printf '{"hookSpecificOutput":{"additionalContext":"%s"}}\n' "$REMINDER"
exit 0
