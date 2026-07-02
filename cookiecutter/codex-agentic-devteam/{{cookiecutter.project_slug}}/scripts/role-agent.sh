#!/usr/bin/env bash
# Generic per-role autonomous agent loop for a queue-first project scope.
#
#   scripts/role-agent.sh <role> <scope>
#
# Watches .queue/pending for a task matching this role AND project_scope, then runs a
# headless `codex exec` agent to claim + complete exactly that one task, and instructs it to
# enqueue one bounded follow-up for the next role (architect->coder->reviewer->tester->ops).
# No GUI windows: this is safe to run from a background/dispatched session.
# No push, no PR, no secrets. Ctrl+C to stop. Idles when no scoped work remains.
set -uo pipefail

ROLE="${1:?usage: role-agent.sh <role> <scope>}"
SCOPE="${2:?usage: role-agent.sh <role> <scope>}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

resolve_codex() {
  if command -v codex >/dev/null 2>&1; then
    command -v codex
    return 0
  fi
  if [ -x "/Applications/Codex.app/Contents/Resources/codex" ]; then
    echo "/Applications/Codex.app/Contents/Resources/codex"
    return 0
  fi
  return 1
}

load_local_env() {
  if [ -f ".env" ]; then
    # Project-local secrets are loaded for child processes only. Do not print them.
    set +u
    set -a
    # shellcheck disable=SC1091
    . ./.env
    set +a
    set -u
  fi
}

alias_for() {
  case "$1" in
    architect) echo fast-planner ;;
    coder)     echo premium-coder ;;
    reviewer)  echo fast-reviewer ;;
    tester)    echo economy-tester ;;
    ops)       echo economy-ops ;;
    *) echo unknown ;;
  esac
}
next_role_for() {
  case "$1" in
    architect) echo coder ;;
    coder)     echo reviewer ;;
    reviewer)  echo tester ;;
    tester)    echo ops ;;
    ops)       echo "" ;;
  esac
}
NEXT="$(next_role_for "$ROLE")"
ALIAS="$(python3 -c "import json,sys;r=json.load(open('docs/controls/model_routing.json'));print(r['roles'][sys.argv[1]].get('alias') or '')" "$ROLE" 2>/dev/null || true)"
if [ -z "$ALIAS" ]; then
  ALIAS="$(alias_for "$ROLE")"
fi
# Resolve the configured model and reasoning effort for this role's tier (model_routing.json).
MODEL="$(python3 -c "import json,sys;r=json.load(open('docs/controls/model_routing.json'));print(r['tiers'][r['roles'][sys.argv[1]]['tier']].get('model','gpt-5.5'))" "$ROLE" 2>/dev/null || echo gpt-5.5)"
REASONING_EFFORT="$(python3 -c "import json,sys;r=json.load(open('docs/controls/model_routing.json'));print(r['tiers'][r['roles'][sys.argv[1]]['tier']].get('reasoning_effort','medium'))" "$ROLE" 2>/dev/null || echo medium)"
if ! CODEX_BIN="$(resolve_codex)"; then
  echo "error: Codex CLI not found. Install Codex CLI, add it to PATH, or install Codex.app at /Applications/Codex.app." >&2
  exit 1
fi
load_local_env

if [ -n "$NEXT" ]; then
  RELAY="When you finish, create and enqueue EXACTLY ONE bounded follow-up task JSON for role ${NEXT} (project_scope ${SCOPE}) via scripts/enqueue.py so the ${NEXT} agent can continue the architect->coder->reviewer->tester->ops chain."
else
  RELAY="You are the FINAL role (ops). Do NOT enqueue any follow-up task — bring the project to closeout."
fi

echo "================================================================"
echo " ${SCOPE} :: ${ROLE} agent (${ALIAS}) — model=${MODEL} reasoning=${REASONING_EFFORT} — headless"
echo " codex: ${CODEX_BIN}"
echo " watching .queue/pending for role=${ROLE} scope=${SCOPE}"
echo " no push / no PR / no secrets — Ctrl+C to stop"
echo "================================================================"

while true; do
  TASK_ID="$(python3 - "$ROLE" "$SCOPE" <<'PY'
import json, sys, glob
role, scope = sys.argv[1], sys.argv[2]
for p in sorted(glob.glob(".queue/pending/*.json")):
    try:
        d = json.load(open(p))
    except Exception:
        continue
    if d.get("role") == role and d.get("project_scope") == scope:
        print(d["id"]); break
PY
)"

  if [ -n "$TASK_ID" ]; then
    echo "[$(date '+%H:%M:%S')] [${ROLE}] >>> running task: ${TASK_ID}"
    PROMPT="You are the ${ROLE} agent in a queue-first multi-agent dev team. Read AGENTS.md, CLAUDE.md when present, and agents/${ROLE}.md rules. Work EXACTLY ONE task: id=${TASK_ID}, role=${ROLE}, project_scope=${SCOPE}.

Steps:
1. Claim it: python3 scripts/claim_task.py ${TASK_ID} --agent cli-${ROLE} --role ${ROLE}
2. Do the work strictly within the task's allowed_paths and acceptance_criteria. Validate each step.
3. Run python3 scripts/control_check.py (and any tests your role requires; if pytest is missing, create a throwaway venv: python3 -m venv /tmp/loop-venv && /tmp/loop-venv/bin/pip install pytest).
4. Apply docs/checklists/pre-push.md. You MAY commit locally. Do NOT push and do NOT open a PR.
5. Close it: python3 scripts/complete_task.py ${TASK_ID} --summary '...' --changed-file ... --validation ...
${RELAY}

HARD RULES: no deploy, no secrets/tokens/env-vars, no DNS/provider API, no git push, no pull request, and stay within this single repo at ${ROOT}. Only ADD commits — never rebase/reset --hard/cherry-pick/drop or undo commits you did not author. Do NOT edit dashboard files (public/*, scripts/archive_tasks.py, scripts/generate_dashboard_status.py, scripts/record_tokens.py, scripts/serve_dashboard_preview.py, scripts/role-agent.sh, scripts/loop.sh). When done, stop."

    TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf '%s\n' "$(cat "agents/${ROLE}.md")" "" "$PROMPT" \
      | RUST_LOG=error AGENT_ROLE="${ROLE}" AGENT_MODEL_ALIAS="${ALIAS}" "${CODEX_BIN}" exec --json \
          --ignore-user-config \
          --model "${MODEL}" \
          --config "model_reasoning_effort=\"${REASONING_EFFORT}\"" \
          --cd "${ROOT}" \
          --skip-git-repo-check \
          --dangerously-bypass-approvals-and-sandbox \
          - \
      | python3 scripts/record_tokens.py "${ROLE}" "${MODEL}" "${TASK_ID}" "${TS}"
    echo "[$(date '+%H:%M:%S')] [${ROLE}] <<< finished ${TASK_ID}; watching for next."
  else
    sleep 6
  fi
done
