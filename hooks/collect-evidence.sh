#!/usr/bin/env bash
# collect-evidence.sh — Capture Bash tool output as evidence for the evaluator agent.
# Fires on PostToolUse for Bash tool calls.

source "$(dirname "$0")/lib.sh"
STATE_DIR="$(state_dir)"

# Read hook input from stdin
HOOK_INPUT=$(cat 2>/dev/null || echo "")

SESSION_ID="$(resolve_session_id "$STATE_DIR")"
[ -z "$SESSION_ID" ] && exit 0

EVIDENCE_DIR="${STATE_DIR}/sessions/${SESSION_ID}/evidence"
mkdir -p "$EVIDENCE_DIR" 2>/dev/null || exit 0

TIMESTAMP="$(timestamp_utc)"
EVIDENCE_FILE="${EVIDENCE_DIR}/${TIMESTAMP}.json"
TMP_FILE="${EVIDENCE_FILE}.tmp"

# Use python3 for reliable JSON handling
python3 -c "
import json, sys, os

hook_input = sys.argv[1]
timestamp = sys.argv[2]
session_id = sys.argv[3]
tmp_file = sys.argv[4]
evidence_file = sys.argv[5]

tool = 'Bash'
command = ''
stdout = ''
stderr = ''
exit_code = 0

try:
    data = json.loads(hook_input) if hook_input.strip() else {}
    tool = data.get('tool_name', data.get('tool', 'Bash'))
    output = data.get('output', data.get('result', ''))
    command = data.get('command', data.get('input', ''))
    exit_code = data.get('exit_code', data.get('exitCode', 0))
    if isinstance(output, str):
        stdout = output
    elif isinstance(output, dict):
        stdout = output.get('stdout', str(output))
        stderr = output.get('stderr', '')
except Exception:
    stdout = hook_input

evidence = {
    'timestamp': timestamp,
    'session_id': session_id,
    'tool': tool,
    'command': command,
    'stdout': stdout,
    'stderr': stderr,
    'exit_code': exit_code
}

with open(tmp_file, 'w') as f:
    json.dump(evidence, f, indent=2, ensure_ascii=False)
os.rename(tmp_file, evidence_file)
" "$HOOK_INPUT" "$TIMESTAMP" "$SESSION_ID" "$TMP_FILE" "$EVIDENCE_FILE" 2>/dev/null

exit 0
