#!/usr/bin/env bash
# session-end.sh — Merge per-session weight updates into state/harness-pool.json.
# Fires on Stop. Uses atomic write (tmp + mv). Creates backup. Cleans old sessions.
# Consume stdin
cat > /dev/null 2>&1 || true

source "$(dirname "${BASH_SOURCE[0]:-$0}")/lib.sh"
PLUGIN_ROOT="$(resolve_plugin_root)"
PROJECT_ROOT="$(resolve_project_root)"
STATE_DIR="$(state_dir)"

# Auto-initialize if state dir is missing or broken; abort silently on failure
if [ -z "$STATE_DIR" ] || [ ! -d "$STATE_DIR" ]; then
  ensure_state_dir "$STATE_DIR" "$PLUGIN_ROOT" 2>/dev/null || exit 0
fi
POOL_FILE="${STATE_DIR}/harness-pool.json"
POOL_BAK="${STATE_DIR}/harness-pool.json.bak"
POOL_TMP="${STATE_DIR}/harness-pool.json.tmp"

SESSION_ID="$(resolve_session_id "$STATE_DIR")"
SESSION_DIR="${STATE_DIR}/sessions/${SESSION_ID:-unknown}"
WEIGHTS_FILE="${SESSION_DIR}/weights.json"
TIMESTAMP="$(timestamp_utc)"

# --- Merge weight updates and eval stats ---
# Proceed if pool file exists — weights.json is optional (eval stats still matter)
if [ -f "$POOL_FILE" ]; then
  # Validate pool JSON is parseable BEFORE backing up (don't backup corrupt files)
  # Pass path via sys.argv to avoid shell injection from apostrophes in paths
  if ! python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$POOL_FILE" 2>/dev/null; then
    echo "[adaptive-harness session-end] Pool file corrupt. Attempting restore from backup." >&2
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
    print(f"[adaptive-harness session-end] Failed to parse pool JSON: {e}", file=sys.stderr)
    sys.exit(0)

if os.path.isfile(weights_file):
    try:
        with open(weights_file, 'r') as f:
            weights = json.load(f)
    except Exception:
        weights = {}
else:
    weights = {}

# Collect per-harness stats from eval files in this session
import glob as _glob
eval_dir = os.path.dirname(weights_file)
harness_stats = {}  # {name: {runs, successes, failures, trailing_consecutive_successes}}
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
        s = harness_stats.setdefault(ch, {"runs": 0, "successes": 0, "failures": 0, "trailing_consecutive_successes": 0})
        s["runs"] += 1
        if passed:
            s["successes"] += 1
            s["trailing_consecutive_successes"] += 1
        else:
            s["failures"] += 1
            s["trailing_consecutive_successes"] = 0

# Collect all harness names that need updating (from weights.json AND eval files)
all_harness_names = set(weights.keys()) | set(harness_stats.keys())

for harness_name in all_harness_names:
    # Find harness in stable or experimental tier
    for pool_tier in ("stable", "experimental"):
        if pool_tier not in pool or harness_name not in pool[pool_tier]:
            continue
        entry = pool[pool_tier][harness_name]

        # Apply weight delta if present in weights.json
        w_data = weights.get(harness_name, {})
        weight_delta = w_data.get("delta", 0) if isinstance(w_data, dict) else 0
        if weight_delta:
            current = entry.get("weight", 1.0)
            entry["weight"] = round(max(0.5, min(2.0, current + weight_delta)), 4)

        # Update counters from eval files
        stats = harness_stats.get(harness_name, {})
        entry["total_runs"] = entry.get("total_runs", 0) + stats.get("runs", 0)
        entry["successes"] = entry.get("successes", 0) + stats.get("successes", 0)
        entry["failures"] = entry.get("failures", 0) + stats.get("failures", 0)

        # Track consecutive successes for promotion
        # trailing_consecutive_successes counts only the unbroken run of
        # successes at the END of this session's eval files for this harness.
        trailing = stats.get("trailing_consecutive_successes", 0)
        if trailing > 0 or stats.get("failures", 0) > 0:
            if stats.get("failures", 0) > 0:
                # Session had at least one failure — reset and start from trailing run
                entry["consecutive_successes"] = trailing
            else:
                # All runs in this session succeeded — extend the existing streak
                entry["consecutive_successes"] = entry.get("consecutive_successes", 0) + trailing
        break

pool["last_updated"] = timestamp
if session_id and session_id != "unknown":
    pool["last_merged_session"] = session_id

# Write atomically (last-writer-wins for concurrent sessions — known v1 limitation)
with open(tmp_file, 'w') as f:
    json.dump(pool, f, indent=2)
os.rename(tmp_file, pool_file)
print(f"[adaptive-harness session-end] Merged session {session_id} weights into pool.")
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

# --- Clean up stale .chain-in-progress marker ---
# If a session ends while a chain marker exists (e.g., abnormal termination),
# remove it so the next session starts clean.
rm -f "${STATE_DIR}/.chain-in-progress" 2>/dev/null || true

# --- Clean up .eval-pending for this session ---
# SESSION_ID was resolved at the top of the script (before any cleanup),
# so it's safe to use here even after .current-session-id was removed.
if [ -n "$SESSION_ID" ] && [ "$SESSION_ID" != "unknown" ]; then
  rm -f "${STATE_DIR}/sessions/${SESSION_ID}/.eval-pending" 2>/dev/null || true
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
