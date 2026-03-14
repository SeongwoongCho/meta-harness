#!/usr/bin/env bash
# collect-evidence.sh — Capture Bash tool output as evidence for the evaluator agent.
# Fires on PostToolUse for Bash tool calls.
set -euo pipefail

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
# Use git root if available, otherwise PWD
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
STATE_DIR="${PROJECT_ROOT}/.meta-harness"

# Resolve session ID: env var takes priority, then fallback to file
SESSION_ID="${CLAUDE_SESSION_ID:-}"
if [ -z "$SESSION_ID" ]; then
  SESSION_ID_FILE="${STATE_DIR}/.current-session-id"
  if [ -f "$SESSION_ID_FILE" ]; then
    SESSION_ID=$(cat "$SESSION_ID_FILE")
  else
    # No session ID available — skip evidence collection silently
    exit 0
  fi
fi

EVIDENCE_DIR="${STATE_DIR}/sessions/${SESSION_ID}/evidence"
mkdir -p "$EVIDENCE_DIR"

TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE_FILE="${EVIDENCE_DIR}/${TIMESTAMP}.json"

# Read hook input from stdin
HOOK_INPUT=$(cat)

# Use python3 for reliable JSON parsing and writing (no sed fragility)
# Output schema matches what agents/evaluator.md expects:
#   {timestamp, session_id, tool, command, stdout, stderr, exit_code}
TMP_FILE="${EVIDENCE_FILE}.tmp"

python3 -c "
import json, sys, os

hook_input = sys.argv[1]
timestamp = sys.argv[2]
session_id = sys.argv[3]
tmp_file = sys.argv[4]
evidence_file = sys.argv[5]

# Parse hook input JSON
tool = 'Bash'
command = ''
stdout = ''
stderr = ''
exit_code = 0
output = ''

try:
    data = json.loads(hook_input) if hook_input.strip() else {}
    # Claude Code hook input structure varies — extract what we can
    tool = data.get('tool_name', data.get('tool', 'Bash'))
    output = data.get('output', data.get('result', ''))
    command = data.get('command', data.get('input', ''))
    exit_code = data.get('exit_code', data.get('exitCode', 0))
    # If output is a string, treat as stdout
    if isinstance(output, str):
        stdout = output
        stderr = ''
    elif isinstance(output, dict):
        stdout = output.get('stdout', str(output))
        stderr = output.get('stderr', '')
except (json.JSONDecodeError, TypeError):
    # If hook input is not JSON, treat entire input as raw output
    stdout = hook_input
    stderr = ''

evidence = {
    'timestamp': timestamp,
    'session_id': session_id,
    'tool': tool,
    'command': command,
    'stdout': stdout,
    'stderr': stderr,
    'exit_code': exit_code
}

# Write atomically
with open(tmp_file, 'w') as f:
    json.dump(evidence, f, indent=2, ensure_ascii=False)
os.rename(tmp_file, evidence_file)
" "$HOOK_INPUT" "$TIMESTAMP" "$SESSION_ID" "$TMP_FILE" "$EVIDENCE_FILE"

# No stdout output — this hook runs silently
exit 0
