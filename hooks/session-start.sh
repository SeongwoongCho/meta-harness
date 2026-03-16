#!/usr/bin/env bash
# session-start.sh — Inject using-adaptive-harness/SKILL.md as additionalContext.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]:-$0}")/lib.sh"
PLUGIN_ROOT="$(resolve_plugin_root)"
SKILL_FILE="${PLUGIN_ROOT}/skills/using-adaptive-harness/SKILL.md"
PROJECT_ROOT="$(resolve_project_root)"
STATE_DIR="$(state_dir)"

# --- Auto-initialize state directory with --general defaults if missing or broken ---
if ! ensure_state_dir "$STATE_DIR" "$PLUGIN_ROOT"; then
  cat <<'INIT_FAIL'
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "[adaptive-harness] ERROR: Failed to auto-initialize .adaptive-harness state directory. Check write permissions and plugin installation."
  }
}
INIT_FAIL
  exit 0
fi

# Generate a stable session ID and create directories
SESSION_ID="${CLAUDE_SESSION_ID:-session-$(date +%s)-$$}"
mkdir -p "${STATE_DIR}/sessions/${SESSION_ID}/evidence" 2>/dev/null || true
printf '%s' "${SESSION_ID}" > "${STATE_DIR}/.current-session-id" 2>/dev/null || true

POOL_FILE="${STATE_DIR}/harness-pool.json"

# L2 fix: Debug log file for graceful-degradation error logging.
# Errors from Python subprocesses are logged here instead of being swallowed silently.
DEBUG_LOG="${STATE_DIR}/.debug-log"

# --- Auto-migration: run migrate.sh when plugin version has changed ---
MIGRATE_NOTICE=""
MIGRATE_SCRIPT="$(dirname "${BASH_SOURCE[0]:-$0}")/migrate.sh"
if [ -f "$MIGRATE_SCRIPT" ] && [ "${ADAPTIVE_HARNESS_SKIP_MIGRATION:-}" != "1" ]; then
  MIGRATE_OUT=$(bash "$MIGRATE_SCRIPT" 2>>"$DEBUG_LOG" || echo "")
  if [ -n "$MIGRATE_OUT" ]; then
    PARSED=$(python3 -c "
import json,sys
d=json.loads(sys.argv[1])
print(d.get('status',''))
print(d.get('from_version','?'))
print(d.get('to_version','?'))
h=d.get('harnesses_added',[])
print(', '.join(h) if h else 'none')
" "$MIGRATE_OUT" 2>>"$DEBUG_LOG" || echo "")
    if [ -n "$PARSED" ]; then
      MIGRATE_STATUS=$(echo "$PARSED" | sed -n '1p')
      if [ "$MIGRATE_STATUS" = "migrated" ]; then
        FROM_VER=$(echo "$PARSED" | sed -n '2p')
        TO_VER=$(echo "$PARSED" | sed -n '3p')
        HARNESSES_ADDED=$(echo "$PARSED" | sed -n '4p')
        MIGRATE_NOTICE="[adaptive-harness] Auto-migration complete: ${FROM_VER} → ${TO_VER}. New harnesses added: ${HARNESSES_ADDED}. "
      fi
    fi
  fi
fi

# --- Fix 6: Apply pending promotion/demotion proposals on session start ---
PROPOSALS_DIR="${STATE_DIR}/evolution-proposals"
LOCAL_HARNESSES_DIR="${STATE_DIR}/harnesses"
if [ -d "$PROPOSALS_DIR" ]; then
  python3 - "$PROPOSALS_DIR" "$POOL_FILE" "$PLUGIN_ROOT/harnesses" "$LOCAL_HARNESSES_DIR" <<'APPLY_PROPOSALS'
import json, sys, os, shutil, glob, re

proposals_dir = sys.argv[1]
pool_file = sys.argv[2]
harnesses_dir = sys.argv[3]       # global plugin harnesses (read-only source)
local_harnesses_dir = sys.argv[4] # project-local harnesses (write target)

os.makedirs(local_harnesses_dir, exist_ok=True)

# M3 fix: Whitelist pattern for harness names — only alphanumeric, hyphens, underscores.
HARNESS_NAME_RE = re.compile(r'^[a-zA-Z0-9_-]+$')

# M1 fix: Validate experimental_harness_path — reject absolute paths and traversals.
def _validate_exp_path(exp_path, local_harnesses_dir):
    """Return (is_valid, resolved_path). Rejects absolute paths and directory traversal.

    exp_path may be in two formats:
      - New format: 'experimental/{variant}' (relative to local_harnesses_dir)
      - Old format: 'harnesses/experimental/{variant}' (legacy, strip leading 'harnesses/')
    """
    if not exp_path:
        return False, ""
    # Reject absolute paths
    if os.path.isabs(exp_path):
        return False, ""
    # Backward compatibility: strip leading 'harnesses/' prefix if present (old format)
    if exp_path.startswith("harnesses/"):
        exp_path = exp_path[len("harnesses/"):]
    allowed_base = os.path.realpath(local_harnesses_dir)
    candidate = os.path.realpath(os.path.join(allowed_base, exp_path))
    # Must stay strictly within allowed_base
    if not candidate.startswith(allowed_base + os.sep):
        return False, ""
    return True, candidate

if not os.path.isfile(pool_file):
    sys.exit(0)

with open(pool_file, 'r') as f:
    pool = json.load(f)

applied = []
for pf in sorted(glob.glob(os.path.join(proposals_dir, "*.json"))):
    try:
        with open(pf, 'r') as f:
            proposal = json.load(f)
    except Exception:
        continue

    if proposal.get("status") != "pending":
        continue

    ptype = proposal.get("proposal_type")
    harness = proposal.get("harness", "")
    exp_path = proposal.get("experimental_harness_path", "")

    # M3 fix: Validate harness name before use in path construction
    if harness and not HARNESS_NAME_RE.match(harness):
        print(f"[adaptive-harness session-start] Rejected proposal {os.path.basename(pf)}: "
              f"invalid harness name {harness!r}", file=sys.stderr)
        proposal["status"] = "rejected"
        with open(pf, 'w') as f:
            json.dump(proposal, f, indent=2)
        continue

    # --- Fix 4: Apply content_modification proposals ---
    if ptype == "content_modification" and exp_path:
        # M1 fix: Validate experimental_harness_path (writes to local_harnesses_dir)
        path_ok, dst_harness = _validate_exp_path(exp_path, local_harnesses_dir)
        if not path_ok:
            print(f"[adaptive-harness session-start] Rejected proposal {os.path.basename(pf)}: "
                  f"unsafe experimental_harness_path {exp_path!r}", file=sys.stderr)
            proposal["status"] = "rejected"
            with open(pf, 'w') as f:
                json.dump(proposal, f, indent=2)
            continue

        # Source reads from global plugin harnesses (read-only)
        src_harness = os.path.join(harnesses_dir, harness)

        if os.path.isdir(src_harness) and not os.path.exists(dst_harness):
            os.makedirs(os.path.dirname(dst_harness.rstrip("/")), exist_ok=True)
            shutil.copytree(src_harness, dst_harness.rstrip("/"))

        change = proposal.get("proposed_change", {})
        target = change.get("file_path", "")
        if target and dst_harness:
            # Rewrite target path to experimental copy
            target_basename = os.path.basename(target)
            exp_target = os.path.join(dst_harness, target_basename)

            ctype = change.get("change_type", "")
            content = change.get("content", "")
            location = change.get("location", "")

            if ctype == "add_section" and os.path.isfile(exp_target) and content:
                with open(exp_target, 'r') as f:
                    original = f.read()
                # Idempotency guard: skip if content already present
                if content.strip() not in original:
                    # Append the new section at the end (safest default)
                    with open(exp_target, 'w') as f:
                        f.write(original.rstrip() + "\n\n" + content + "\n")
            elif ctype == "modify_trigger" and os.path.isfile(exp_target):
                old_val = change.get("current_value", "")
                new_val = change.get("new_value", "")
                if old_val and new_val:
                    with open(exp_target, 'r') as f:
                        text = f.read()
                    text = text.replace(old_val, new_val)
                    with open(exp_target, 'w') as f:
                        f.write(text)

        # Register in experimental pool
        exp_name = os.path.basename(dst_harness.rstrip("/")) if dst_harness else ""
        if exp_name and "experimental" in pool:
            pool["experimental"][exp_name] = {
                "weight": 1.0, "total_runs": 0, "successes": 0,
                "failures": 0, "consecutive_successes": 0,
                "base_harness": harness
            }

        proposal["status"] = "applied"
        applied.append(pf)

    # --- Harness genesis: Create new harness from proposal ---
    elif ptype == "new_harness" and exp_path:
        # M1 fix: Validate experimental_harness_path (writes to local_harnesses_dir)
        path_ok, dst_harness = _validate_exp_path(exp_path, local_harnesses_dir)
        if not path_ok:
            print(f"[adaptive-harness session-start] Rejected proposal {os.path.basename(pf)}: "
                  f"unsafe experimental_harness_path {exp_path!r}", file=sys.stderr)
            proposal["status"] = "rejected"
            with open(pf, 'w') as f:
                json.dump(proposal, f, indent=2)
            continue

        if not os.path.exists(dst_harness):
            os.makedirs(dst_harness, exist_ok=True)
            proposed = proposal.get("proposed_harness", {})

            # Write agent.md
            agent_content = proposed.get("agent_md", "")
            if agent_content:
                name = proposed.get("name", harness)
                desc = proposed.get("description", "")
                model = proposed.get("model", "claude-sonnet-4-6")
                header = f"---\nname: {name}\ndescription: \"{desc}\"\nmodel: {model}\n---\n\n"
                with open(os.path.join(dst_harness, "agent.md"), 'w') as f:
                    f.write(header + agent_content)

            # Write skill.md
            skill_content = proposed.get("skill_md", "")
            if skill_content:
                with open(os.path.join(dst_harness, "skill.md"), 'w') as f:
                    f.write(skill_content)

            # Write contract.yaml
            contract = proposed.get("contract_yaml", {})
            if contract:
                import yaml
                contract_full = {
                    "name": proposed.get("name", harness),
                    "version": "1.0.0",
                    "pool": "experimental",
                    **contract
                }
                try:
                    with open(os.path.join(dst_harness, "contract.yaml"), 'w') as f:
                        yaml.dump(contract_full, f, default_flow_style=False, allow_unicode=True)
                except ImportError:
                    # Fallback: write as simple text if yaml not available
                    with open(os.path.join(dst_harness, "contract.yaml"), 'w') as f:
                        f.write(json.dumps(contract_full, indent=2))

            # Write metadata.json
            with open(os.path.join(dst_harness, "metadata.json"), 'w') as f:
                json.dump({
                    "name": proposed.get("name", harness),
                    "version": "1.0.0",
                    "pool": "experimental",
                    "source_harnesses": proposal.get("evidence", {}).get("source_harnesses", []),
                    "created_by": "evolution-manager",
                    "created_at": proposal.get("created_at", "")
                }, f, indent=2)

        # Register in experimental pool
        exp_name = proposed.get("name", harness) if "proposed_harness" in proposal else os.path.basename(dst_harness.rstrip("/"))
        if exp_name and "experimental" in pool:
            pool["experimental"][exp_name] = {
                "weight": 1.0, "total_runs": 0, "successes": 0,
                "failures": 0, "consecutive_successes": 0,
                "base_harness": None,
                "genesis": True,
                "source_harnesses": proposal.get("evidence", {}).get("source_harnesses", [])
            }

        proposal["status"] = "applied"
        applied.append(pf)

    # --- Fix 6: Execute promotion proposals ---
    elif ptype == "promotion":
        # Look for experimental variant in local harnesses first, then global
        local_exp_base = os.path.join(local_harnesses_dir, "experimental")
        exp_dir = os.path.join(local_exp_base, harness)
        for exp_candidate in glob.glob(os.path.join(local_exp_base, f"{harness}-*")):
            if os.path.isdir(exp_candidate):
                exp_dir = exp_candidate
                break

        # Promote to local stable override (never modifies global plugin cache)
        local_stable_dir = os.path.join(local_harnesses_dir, harness)
        if os.path.isdir(exp_dir):
            # Backup current local stable override if present
            backup = local_stable_dir + ".bak"
            if os.path.isdir(local_stable_dir):
                if os.path.exists(backup):
                    shutil.rmtree(backup)
                shutil.copytree(local_stable_dir, backup)
                shutil.rmtree(local_stable_dir)
            shutil.copytree(exp_dir, local_stable_dir)
            shutil.rmtree(exp_dir)

            # Move from experimental to stable in pool
            exp_name = os.path.basename(exp_dir)
            if exp_name in pool.get("experimental", {}):
                entry = pool["experimental"].pop(exp_name)
                entry["consecutive_successes"] = 0  # reset after promotion
                pool["stable"][harness] = entry

        proposal["status"] = "applied"
        applied.append(pf)

    # --- Fix 6: Execute demotion proposals ---
    elif ptype == "demotion":
        local_exp_base = os.path.join(local_harnesses_dir, "experimental")
        local_stable_dir = os.path.join(local_harnesses_dir, harness)
        exp_dir = os.path.join(local_exp_base, harness + "-demoted")
        # Only copy if a local stable override exists (don't touch global plugin cache)
        if os.path.isdir(local_stable_dir) and not os.path.exists(exp_dir):
            os.makedirs(local_exp_base, exist_ok=True)
            shutil.copytree(local_stable_dir, exp_dir)
            # Move from stable to experimental in pool
            if harness in pool.get("stable", {}):
                entry = pool["stable"].pop(harness)
                pool["experimental"][harness + "-demoted"] = entry
        elif not os.path.isdir(local_stable_dir):
            # No local override — pool-only operation (move entry if present)
            if harness in pool.get("stable", {}):
                entry = pool["stable"].pop(harness)
                pool["experimental"][harness + "-demoted"] = entry

        proposal["status"] = "applied"
        applied.append(pf)

    # Write back updated proposal status
    if proposal.get("status") == "applied":
        with open(pf, 'w') as f:
            json.dump(proposal, f, indent=2)

if applied:
    with open(pool_file, 'w') as f:
        json.dump(pool, f, indent=2)
    names = [os.path.basename(p) for p in applied]
    print(f"[adaptive-harness session-start] Applied {len(applied)} proposals: {', '.join(names)}", file=sys.stderr)
APPLY_PROPOSALS
fi

# --- Clean up stale .chain-in-progress from prior sessions ---
# If a previous session ended abnormally mid-chain, the marker persists.
# New sessions never inherit chain state, so always remove on startup.
rm -f "${STATE_DIR}/.chain-in-progress" 2>/dev/null || true

# --- Pipeline mode check ---
# Only inject full SKILL.md (auto-mode) if .pipeline-mode is "auto".
# Otherwise, inject a lightweight message indicating adaptive-harness is available but not auto-routing.
PIPELINE_MODE=""
MODE_FILE="${STATE_DIR}/.pipeline-mode"
[ -f "$MODE_FILE" ] && PIPELINE_MODE=$(cat "$MODE_FILE" 2>/dev/null)

# Also clear stale "run" mode on session start (run is one-shot, shouldn't persist across sessions)
if [ "$PIPELINE_MODE" = "run" ]; then
  rm -f "$MODE_FILE"
  PIPELINE_MODE=""
fi

# Escape for JSON using bash parameter substitution (same pattern as superpowers)
escape_for_json() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\n'/\\n}"
    s="${s//$'\r'/\\r}"
    s="${s//$'\t'/\\t}"
    printf '%s' "$s"
}

if [ "$PIPELINE_MODE" = "auto" ]; then
  # Auto-mode: inject full SKILL.md for pipeline orchestration
  if [ ! -f "$SKILL_FILE" ]; then
    cat <<'FALLBACK'
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "[adaptive-harness] Auto-mode enabled but SKILL.md not found."
  }
}
FALLBACK
    exit 0
  fi

  # Use python3 for safe substitution — sed's replacement field expands & and
  # breaks on | in the value, which can occur in PLUGIN_ROOT paths.
  SKILL_CONTENT=$(python3 -c "
import sys
with open(sys.argv[1]) as f:
    print(f.read().replace('{{PLUGIN_ROOT}}', sys.argv[2]), end='')
" "$SKILL_FILE" "$PLUGIN_ROOT")
  MIGRATE_NOTICE_ESCAPED=$(escape_for_json "$MIGRATE_NOTICE")
  ESCAPED=$(escape_for_json "$SKILL_CONTENT")

  cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "${MIGRATE_NOTICE_ESCAPED}${ESCAPED}"
  }
}
EOF
else
  # No auto-mode: lightweight message, adaptive-harness available on demand
  MIGRATE_NOTICE_ESCAPED=$(escape_for_json "$MIGRATE_NOTICE")
  cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "${MIGRATE_NOTICE_ESCAPED}[adaptive-harness] Plugin loaded. Auto-mode is OFF. Use /adaptive-harness:run <task> for one-shot pipeline execution, or enable auto-mode with: printf 'auto' > .adaptive-harness/.pipeline-mode"
  }
}
EOF
fi

exit 0
