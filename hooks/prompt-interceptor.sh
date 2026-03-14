#!/usr/bin/env bash
# prompt-interceptor.sh — Reinforce meta-harness routing on every user message.
# Run: chmod +x hooks/prompt-interceptor.sh
# Output must be under 500 bytes.
set -euo pipefail

REMINDER="[meta-harness] Follow the using-meta-harness-default skill: classify this task via the router agent and route it through the meta-harness pipeline before responding directly."

printf '{"hookSpecificOutput":{"additionalContext":"%s"}}\n' "$REMINDER"
