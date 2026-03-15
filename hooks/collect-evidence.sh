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

# Use python3 for reliable JSON handling; pass hook input via stdin to avoid arg length limits
printf '%s' "$HOOK_INPUT" | python3 -c "
import json, sys, os

hook_input = sys.stdin.read()
timestamp = sys.argv[1]
session_id = sys.argv[2]
tmp_file = sys.argv[3]
evidence_file = sys.argv[4]

tool = 'Bash'
command = ''
stdout = ''
stderr = ''
exit_code = 0

try:
    data = json.loads(hook_input) if hook_input.strip() else {}
    tool = data.get('tool_name', data.get('tool', 'Bash'))

    # Extract from nested tool_input (Claude Code PostToolUse format)
    tool_input = data.get('tool_input', {})
    tool_response = data.get('tool_response', {})

    if isinstance(tool_input, dict):
        command = tool_input.get('command', '')
    else:
        command = data.get('command', data.get('input', ''))

    if isinstance(tool_response, dict):
        raw_output = tool_response.get('output', tool_response.get('stdout', ''))
        exit_code = tool_response.get('exitCode', tool_response.get('exit_code', 0))
        stderr = tool_response.get('stderr', '')
        if isinstance(raw_output, str):
            stdout = raw_output
        elif isinstance(raw_output, dict):
            stdout = raw_output.get('stdout', str(raw_output))
            stderr = stderr or raw_output.get('stderr', '')
    else:
        # Fallback: try top-level fields (legacy format)
        output = data.get('output', data.get('result', ''))
        exit_code = data.get('exit_code', data.get('exitCode', 0))
        if isinstance(output, str):
            stdout = output
        elif isinstance(output, dict):
            stdout = output.get('stdout', str(output))
            stderr = output.get('stderr', '')
except Exception as e:
    stdout = hook_input
    stderr = str(e)

# Truncate large outputs to keep evidence files manageable (max 4KB per field)
MAX_LEN = 4096
if len(stdout) > MAX_LEN:
    stdout = stdout[:MAX_LEN] + '... [truncated]'
if len(stderr) > MAX_LEN:
    stderr = stderr[:MAX_LEN] + '... [truncated]'

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
" "$TIMESTAMP" "$SESSION_ID" "$TMP_FILE" "$EVIDENCE_FILE" 2>/dev/null

exit 0
