#!/usr/bin/env bash
# session-end.sh — Merge per-session weight updates into state/harness-pool.json.
# Fires on Stop. Uses atomic write (tmp + mv). Creates backup. Cleans old sessions.
# Consume stdin
cat > /dev/null 2>&1 || true

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
# Use git root if available, otherwise PWD
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
STATE_DIR="${PROJECT_ROOT}/.meta-harness"
POOL_FILE="${STATE_DIR}/harness-pool.json"
POOL_BAK="${STATE_DIR}/harness-pool.json.bak"
POOL_TMP="${STATE_DIR}/harness-pool.json.tmp"

# Resolve session ID
SESSION_ID="${CLAUDE_SESSION_ID:-}"
if [ -z "$SESSION_ID" ]; then
  SESSION_ID_FILE="${STATE_DIR}/.current-session-id"
  if [ -f "$SESSION_ID_FILE" ]; then
    SESSION_ID=$(cat "$SESSION_ID_FILE")
  fi
fi

SESSION_DIR="${STATE_DIR}/sessions/${SESSION_ID:-unknown}"
WEIGHTS_FILE="${SESSION_DIR}/weights.json"
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)

# --- Merge weight updates ---
# Only merge if both pool file and session weights file exist
if [ -f "$POOL_FILE" ] && [ -f "$WEIGHTS_FILE" ]; then
  # Validate pool JSON is parseable BEFORE backing up (don't backup corrupt files)
  if ! python3 -c "import json; json.load(open('$POOL_FILE'))" 2>/dev/null; then
    echo "[meta-harness session-end] Pool file corrupt. Attempting restore from backup." >&2
    if [ -f "$POOL_BAK" ]; then
      cp "$POOL_BAK" "$POOL_FILE"
    fi
    exit 0
  fi

  # Backup AFTER validation (backup is always a known-good copy)
  cp "$POOL_FILE" "$POOL_BAK"

  # Pass all variables safely via command-line arguments (no shell injection risk)
  python3 - "$POOL_FILE" "$WEIGHTS_FILE" "$POOL_TMP" "$TIMESTAMP" "${SESSION_ID:-unknown}" <<'PYEOF'
import json, sys, os

pool_file = sys.argv[1]
weights_file = sys.argv[2]
tmp_file = sys.argv[3]
timestamp = sys.argv[4]
session_id = sys.argv[5]

try:
    with open(pool_file, 'r') as f:
        pool = json.load(f)
except Exception as e:
    print(f"[meta-harness session-end] Failed to parse pool JSON: {e}", file=sys.stderr)
    sys.exit(0)

try:
    with open(weights_file, 'r') as f:
        weights = json.load(f)
except Exception:
    weights = {}

# Apply weight updates from session
# Pool format: {"stable": {"harness-name": {...}}, "experimental": {"harness-name": {...}}}
for pool_tier in ("stable", "experimental"):
    if pool_tier not in pool:
        continue
    for harness_name, delta in weights.get(pool_tier, {}).items():
        if harness_name in pool[pool_tier]:
            entry = pool[pool_tier][harness_name]
            # Apply delta (bounded to [0.5, 2.0] range)
            current = entry.get("weight", 1.0)
            new_weight = max(0.5, min(2.0, current + delta.get("weight_delta", 0)))
            entry["weight"] = round(new_weight, 4)
            # Update counters
            entry["successes"] = entry.get("successes", 0) + delta.get("successes", 0)
            entry["failures"] = entry.get("failures", 0) + delta.get("failures", 0)
            entry["total_runs"] = entry.get("total_runs", 0) + delta.get("runs", 0)
            # Track consecutive successes for promotion
            if delta.get("last_result") == "success":
                entry["consecutive_successes"] = entry.get("consecutive_successes", 0) + 1
            elif delta.get("last_result") == "failure":
                entry["consecutive_successes"] = 0

pool["last_updated"] = timestamp
pool["last_merged_session"] = session_id

# Write atomically (last-writer-wins for concurrent sessions — known v1 limitation)
with open(tmp_file, 'w') as f:
    json.dump(pool, f, indent=2)
os.rename(tmp_file, pool_file)
print(f"[meta-harness session-end] Merged session {session_id} weights into pool.")
PYEOF

elif [ ! -f "$POOL_FILE" ]; then
  :
fi

# --- Clean up old session directories (older than 30 days) ---
if [ -d "${STATE_DIR}/sessions" ]; then
  find "${STATE_DIR}/sessions" -maxdepth 1 -type d -mtime +30 -not -path "${STATE_DIR}/sessions" \
    -exec rm -rf {} + 2>/dev/null || true
fi

# --- Clean up current session ID file ---
if [ -f "${STATE_DIR}/.current-session-id" ]; then
  rm -f "${STATE_DIR}/.current-session-id"
fi

exit 0
