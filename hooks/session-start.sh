#!/usr/bin/env bash
# session-start.sh — Inject using-meta-harness-default/SKILL.md as additionalContext.

# Consume stdin
cat > /dev/null 2>&1 || true

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
SKILL_FILE="${PLUGIN_ROOT}/skills/using-meta-harness-default/SKILL.md"
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
STATE_DIR="${PROJECT_ROOT}/.meta-harness"

# Generate a stable session ID and write for other hooks
SESSION_ID="${CLAUDE_SESSION_ID:-}"
if [ -z "$SESSION_ID" ]; then
  SESSION_ID="session-$(date +%s)-$$"
fi
mkdir -p "${STATE_DIR}/sessions/${SESSION_ID}/evidence" 2>/dev/null || true
printf '%s' "${SESSION_ID}" > "${STATE_DIR}/.current-session-id" 2>/dev/null || true

# Read SKILL.md — exit cleanly if not found
if [ ! -f "$SKILL_FILE" ]; then
  exit 0
fi

# Use python3 for reliable JSON escaping (no sed fragility)
python3 -c "
import json, sys
try:
    with open(sys.argv[1], 'r') as f:
        content = f.read()
    output = {'hookSpecificOutput': {'additionalContext': content}}
    print(json.dumps(output))
except Exception:
    print('{\"hookSpecificOutput\":{\"additionalContext\":\"[meta-harness] Skill loaded.\"}}')
" "$SKILL_FILE"

exit 0
