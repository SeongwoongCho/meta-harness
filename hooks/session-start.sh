#!/usr/bin/env bash
# session-start.sh — Inject using-adaptive-harness/SKILL.md as additionalContext.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]:-$0}")/lib.sh"
PLUGIN_ROOT="$(resolve_plugin_root)"
SKILL_FILE="${PLUGIN_ROOT}/skills/using-adaptive-harness/SKILL.md"
PROJECT_ROOT="$(resolve_project_root)" || PROJECT_ROOT="$PWD"
STATE_DIR="$(state_dir)" || {
  # state_dir() can return 1 if CWD is inside plugin cache. Emit fallback JSON and exit.
  cat <<'FALLBACK_SD'
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "[adaptive-harness] Plugin loaded but state directory could not be resolved. Use /adaptive-harness:init to set up."
  }
}
FALLBACK_SD
  exit 0
}

# Generate a stable session ID and create directories
SESSION_ID="${CLAUDE_SESSION_ID:-session-$(date +%s)-$$}"
mkdir -p "${STATE_DIR}/sessions/${SESSION_ID}/evidence" 2>/dev/null || true

# Write plugin root path so skills/agents can discover it at runtime
printf '%s' "${PLUGIN_ROOT}" > "${STATE_DIR}/.plugin-root" 2>/dev/null || true
mkdir -p "${STATE_DIR}/evaluation-logs" 2>/dev/null || true
mkdir -p "${STATE_DIR}/evolution-proposals" 2>/dev/null || true
printf '%s' "${SESSION_ID}" > "${STATE_DIR}/.current-session-id" 2>/dev/null || true

# --- Fix 1: Bootstrap harness-pool.json if it doesn't exist ---
POOL_FILE="${STATE_DIR}/harness-pool.json"
if [ ! -f "$POOL_FILE" ]; then
  HARNESS_DIR="${PLUGIN_ROOT}/harnesses"
  if [ -d "$HARNESS_DIR" ]; then
    python3 - "$HARNESS_DIR" "$POOL_FILE" <<'BOOTSTRAP_POOL'
import json, sys, os
harnesses_dir, pool_file = sys.argv[1], sys.argv[2]
pool = {"stable": {}, "experimental": {}, "last_updated": None, "last_merged_session": None}
skip = {"experimental", "archived", "__pycache__", "_shared"}
for name in sorted(os.listdir(harnesses_dir)):
    full = os.path.join(harnesses_dir, name)
    if os.path.isdir(full) and name not in skip and not name.startswith("."):
        pool["stable"][name] = {
            "weight": 1.0,
            "total_runs": 0,
            "successes": 0,
            "failures": 0,
            "consecutive_successes": 0
        }
with open(pool_file, 'w') as f:
    json.dump(pool, f, indent=2)
print(f"[adaptive-harness session-start] Bootstrapped harness-pool.json with {len(pool['stable'])} stable harnesses.", file=sys.stderr)
BOOTSTRAP_POOL
  fi
fi

# --- Auto-migration: run migrate.sh when plugin version has changed ---
MIGRATE_NOTICE=""
MIGRATE_SCRIPT="$(dirname "${BASH_SOURCE[0]:-$0}")/migrate.sh"
if [ -f "$MIGRATE_SCRIPT" ] && [ "${ADAPTIVE_HARNESS_SKIP_MIGRATION:-}" != "1" ]; then
  MIGRATE_OUT=$(bash "$MIGRATE_SCRIPT" 2>/dev/null || echo "")
  if [ -n "$MIGRATE_OUT" ]; then
    PARSED=$(python3 -c "
import json,sys
d=json.loads(sys.argv[1])
print(d.get('status',''))
print(d.get('from_version','?'))
print(d.get('to_version','?'))
h=d.get('harnesses_added',[])
print(', '.join(h) if h else 'none')
" "$MIGRATE_OUT" 2>/dev/null || echo "")
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
if [ -d "$PROPOSALS_DIR" ]; then
  python3 - "$PROPOSALS_DIR" "$POOL_FILE" "$PLUGIN_ROOT/harnesses" <<'APPLY_PROPOSALS'
import json, sys, os, shutil, glob

proposals_dir = sys.argv[1]
pool_file = sys.argv[2]
harnesses_dir = sys.argv[3]

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

    # --- Fix 4: Apply content_modification proposals ---
    if ptype == "content_modification" and exp_path:
        src_harness = os.path.join(harnesses_dir, harness)
        dst_harness = os.path.join(os.path.dirname(harnesses_dir), exp_path) if not os.path.isabs(exp_path) else exp_path
        # Resolve relative to plugin root
        if not os.path.isabs(dst_harness):
            dst_harness = os.path.join(os.path.dirname(harnesses_dir), exp_path)

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
        dst_harness = os.path.join(os.path.dirname(harnesses_dir), exp_path) if not os.path.isabs(exp_path) else exp_path
        if not os.path.isabs(dst_harness):
            dst_harness = os.path.join(os.path.dirname(harnesses_dir), exp_path)

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
        exp_dir = os.path.join(harnesses_dir, "experimental", harness)
        # Find the experimental variant
        for exp_candidate in glob.glob(os.path.join(harnesses_dir, "experimental", f"{harness}-*")):
            if os.path.isdir(exp_candidate):
                exp_dir = exp_candidate
                break

        stable_dir = os.path.join(harnesses_dir, harness)
        if os.path.isdir(exp_dir):
            # Backup current stable
            backup = stable_dir + ".bak"
            if os.path.isdir(stable_dir):
                if os.path.exists(backup):
                    shutil.rmtree(backup)
                shutil.copytree(stable_dir, backup)
                shutil.rmtree(stable_dir)
            shutil.copytree(exp_dir, stable_dir)
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
        stable_dir = os.path.join(harnesses_dir, harness)
        exp_dir = os.path.join(harnesses_dir, "experimental", harness + "-demoted")
        if os.path.isdir(stable_dir) and not os.path.exists(exp_dir):
            os.makedirs(os.path.join(harnesses_dir, "experimental"), exist_ok=True)
            shutil.copytree(stable_dir, exp_dir)
            # Move from stable to experimental in pool
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
