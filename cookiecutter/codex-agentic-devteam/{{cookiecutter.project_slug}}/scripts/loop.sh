#!/usr/bin/env bash
# Dispatch-friendly plan -> build -> track workflow for the agentic dev team.
# Headless (no GUI windows), so it runs from a dispatched/background session.
#
#   scripts/loop.sh plan  <scope> "<objective>"   # architect designs it -> review on the dashboard
#   scripts/loop.sh build <scope>                 # coder -> reviewer -> tester -> ops execute the plan
#   scripts/loop.sh status <scope>                # what's running + queue counts for the scope
#   scripts/loop.sh stop  <scope>                 # stop this scope's agents
#
# Plan phase runs ONLY the architect: it writes a design + enqueues one bounded coder
# follow-up, then idles. You review the design (dashboard / docs/architecture), then run
# build to execute. No push, no PR, no secrets.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

CMD="${1:-}"
SCOPE="${2:-}"

logdir_for() { echo "/tmp/agent-loop-${1}"; }

start_role() {  # <role> <scope>
  local role="$1" scope="$2" logdir
  logdir="$(logdir_for "$scope")"
  mkdir -p "$logdir"
  if pgrep -f "role-agent.sh ${role} ${scope}" >/dev/null 2>&1; then
    echo "[${role}] already running"
    return
  fi
  nohup bash scripts/role-agent.sh "$role" "$scope" > "${logdir}/${role}.log" 2>&1 &
  echo "[${role}] started (pid $!) -> ${logdir}/${role}.log"
}

case "$CMD" in
  plan)
    OBJ="${3:-}"
    [ -n "$SCOPE" ] && [ -n "$OBJ" ] || { echo "usage: loop.sh plan <scope> \"<objective>\""; exit 2; }
    mkdir -p "docs/loops/${SCOPE}"
    SEED="docs/loops/${SCOPE}/seed-architect-0001.json"
    if [ -f "$SEED" ]; then
      echo "seed exists: ${SEED} (reusing — delete it to re-plan from scratch)"
    else
      python3 - "$SCOPE" "$OBJ" "$SEED" <<'PY'
import json, sys
scope, obj, out = sys.argv[1], sys.argv[2], sys.argv[3]
seed = {
    "id": f"{scope}-architect-0001",
    "title": f"Design {scope}",
    "role": "architect",
    "model_tier": "gpt-5.4-high",
    "model_alias": "architect-gpt-5.4-high",
    "status": "pending",
    "created_at": "2026-06-30T20:00:00+03:00",
    "project_scope": scope,
    "objective": obj,
    "allowed_paths": ["docs/architecture/", f"docs/loops/{scope}/", ".queue/"],
    "acceptance_criteria": [
        "Produce a concrete design: data/interface contract, a file-level implementation plan, and acceptance criteria for the implementation.",
        "Include at least one Mermaid diagram (a ```mermaid fenced block) in the design doc that visualizes the plan (e.g. page/section flow or component/data flow), so it renders on the dashboard's Plan view.",
        f"Create EXACTLY ONE bounded Coder follow-up task (project_scope {scope}) referencing this design.",
        "EXPLICIT FORBIDDEN: no deploy, no secret/token/env-var/credential, no DNS/provider API, no git push, no pull request, and no code implementation in this architect task.",
    ],
    "context": {"project": scope, "note": "Plan only; implementation is the coder follow-up."},
}
with open(out, "w", encoding="utf-8") as fh:
    fh.write(json.dumps(seed, indent=2) + "\n")
print(f"wrote seed: {out}")
PY
    fi
    SID="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['id'])" "$SEED")"
    if ls .queue/pending/"$SID".json .queue/in-progress/"$SID".json .queue/done/"$SID".json >/dev/null 2>&1; then
      echo "seed ${SID} already in queue (skip enqueue)"
    else
      python3 scripts/enqueue.py "$SEED"
    fi
    start_role architect "$SCOPE"
    echo
    echo "PLAN phase running — the architect is designing '${SCOPE}'."
    echo "watch:  tail -f $(logdir_for "$SCOPE")/architect.log   (or the dashboard ticker, scope=${SCOPE})"
    echo "review: docs/architecture/  +  docs/loops/${SCOPE}/"
    echo "next:   scripts/loop.sh build ${SCOPE}   (when the design looks good)"
    ;;

  build)
    [ -n "$SCOPE" ] || { echo "usage: loop.sh build <scope>"; exit 2; }
    for role in coder reviewer tester ops; do
      start_role "$role" "$SCOPE"
    done
    echo
    echo "BUILD phase running for '${SCOPE}' — coder -> reviewer -> tester -> ops."
    echo "track:  dashboard ticker + Token Performance (scope=${SCOPE})"
    echo "stop:   scripts/loop.sh stop ${SCOPE}"
    ;;

  status)
    [ -n "$SCOPE" ] || { echo "usage: loop.sh status <scope>"; exit 2; }
    echo "agents running for ${SCOPE}:"
    pgrep -fl "role-agent.sh .* ${SCOPE}" || echo "  none"
    echo "queue (${SCOPE}):"
    for d in pending in-progress done failed; do
      n="$(ls ".queue/${d}/" 2>/dev/null | grep -c "^${SCOPE}-" || true)"
      echo "  ${d}: ${n}"
    done
    ;;

  stop)
    [ -n "$SCOPE" ] || { echo "usage: loop.sh stop <scope>"; exit 2; }
    pkill -f "role-agent.sh .* ${SCOPE}" && echo "stopped ${SCOPE} agents" || echo "no agents running for ${SCOPE}"
    ;;

  *)
    echo "usage: loop.sh {plan <scope> \"<objective>\" | build <scope> | status <scope> | stop <scope>}"
    exit 2
    ;;
esac
