#!/usr/bin/env bash
# session-end.sh — Merge per-session weight updates into state/harness-pool.json.
# Fires on Stop. Uses atomic write (tmp + mv). Creates backup. Cleans old sessions.
# Consume stdin
cat > /dev/null 2>&1 || true

source "$(dirname "$0")/lib.sh"
PROJECT_ROOT="$(resolve_project_root)"
STATE_DIR="$(state_dir)"
POOL_FILE="${STATE_DIR}/harness-pool.json"
POOL_BAK="${STATE_DIR}/harness-pool.json.bak"
POOL_TMP="${STATE_DIR}/harness-pool.json.tmp"

SESSION_ID="$(resolve_session_id "$STATE_DIR")"
SESSION_DIR="${STATE_DIR}/sessions/${SESSION_ID:-unknown}"
WEIGHTS_FILE="${SESSION_DIR}/weights.json"
TIMESTAMP="$(timestamp_utc)"

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

# Collect per-harness stats from eval files in this session
import glob as _glob
eval_dir = os.path.dirname(weights_file)
harness_stats = {}  # {name: {runs, successes, failures, last_result}}
for ef in sorted(_glob.glob(os.path.join(eval_dir, "eval-*.json"))):
    try:
        with open(ef) as _f:
            ev = json.load(_f)
    except Exception:
        continue
    if ev.get("fast_path"):
        continue
    passed = ev.get("quality_gate_passed", True)
    # Credit each harness in a chain, or the single harness
    chain = ev.get("harness_chain")
    if not chain:
        h = ev.get("harness", "")
        # Parse "chain:a+b+c" format into individual harness names
        if h.startswith("chain:"):
            chain = h[len("chain:"):].split("+")
        elif h and h != "fast-path":
            chain = [h]
        else:
            chain = []
    for ch in chain:
        s = harness_stats.setdefault(ch, {"runs": 0, "successes": 0, "failures": 0, "last_result": None})
        s["runs"] += 1
        if passed:
            s["successes"] += 1
            s["last_result"] = "success"
        else:
            s["failures"] += 1
            s["last_result"] = "failure"

# Apply weight deltas and counters
# weights.json format: flat {harness_name: {delta: N, reason: "..."}}
for harness_name, w_data in weights.items():
    weight_delta = w_data.get("delta", 0) if isinstance(w_data, dict) else 0
    # Find harness in stable or experimental tier
    for pool_tier in ("stable", "experimental"):
        if pool_tier not in pool or harness_name not in pool[pool_tier]:
            continue
        entry = pool[pool_tier][harness_name]
        # Apply delta (bounded to [0.5, 2.0] range)
        current = entry.get("weight", 1.0)
        entry["weight"] = round(max(0.5, min(2.0, current + weight_delta)), 4)
        # Update counters from eval files
        stats = harness_stats.get(harness_name, {})
        entry["total_runs"] = entry.get("total_runs", 0) + stats.get("runs", 0)
        entry["successes"] = entry.get("successes", 0) + stats.get("successes", 0)
        entry["failures"] = entry.get("failures", 0) + stats.get("failures", 0)
        # Track consecutive successes for promotion
        lr = stats.get("last_result")
        if lr == "success":
            entry["consecutive_successes"] = entry.get("consecutive_successes", 0) + stats.get("successes", 0)
        elif lr == "failure":
            entry["consecutive_successes"] = 0
        break

pool["last_updated"] = timestamp
pool["last_merged_session"] = session_id

# Write atomically (last-writer-wins for concurrent sessions — known v1 limitation)
with open(tmp_file, 'w') as f:
    json.dump(pool, f, indent=2)
os.rename(tmp_file, pool_file)
print(f"[meta-harness session-end] Merged session {session_id} weights into pool.")
PYEOF

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

# --- Clean up stale "run" mode (safety net) ---
# If pipeline mode is "run" at session end, the orchestrator failed to clean up.
# Clear it so the next session starts clean. "auto" mode is intentionally persistent.
MODE_FILE="${STATE_DIR}/.pipeline-mode"
if [ -f "$MODE_FILE" ]; then
  CURRENT_MODE=$(cat "$MODE_FILE" 2>/dev/null)
  if [ "$CURRENT_MODE" = "run" ]; then
    rm -f "$MODE_FILE"
  fi
fi

exit 0
