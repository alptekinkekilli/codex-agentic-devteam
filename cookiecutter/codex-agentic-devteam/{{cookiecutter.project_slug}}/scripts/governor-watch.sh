#!/usr/bin/env bash
# governor-watch.sh — the governor's event-based queue watcher.
#
# Exits on the FIRST signal so the governor is notified IMMEDIATELY. Do not
# use a single long-lived watcher that logs interim findings to a file — the
# notification only fires when the process exits, so the pre-claim audit
# window (a new pending task that should be inspected before a driver claims
# it) passes silently. Pattern: run in background → first event exits → the
# governor audits → restart the watcher.
#
# Signals (first one wins):
#   NEW_PENDING  — an unexpected task appeared in .queue/pending/
#                  (pre-claim audit window: check tier/alias against
#                  docs/controls/model_routing.json, ID uniqueness against
#                  done/failed, allowed_paths against role_capabilities.json)
#   NEW_FAILED   — a new file appeared in .queue/failed/ (beyond ignore list)
#   TARGET_DONE  — the target task reached .queue/done/
#   DRIVER_DEAD  — a watched driver process died (optional)
#
# Usage:
#   bash scripts/governor-watch.sh \
#     [--done <task-id-substring>]        # exit when this id reaches done/
#     [--expect-pending "<id1|id2>"]      # pending tasks that are EXPECTED
#     [--ignore-failed "<id1|id2>"]       # already-known failed records
#     [--driver-pattern "<pgrep pattern>"]# exit if this process dies
#     [--interval <seconds>]              # poll interval (default 5)
#
# Example (watch one phase's build chain):
#   bash scripts/governor-watch.sh --done ops-0004 \
#     --expect-pending "coder-0006" --ignore-failed "coder-0002|coder-0004"
#
# Output is a single "EVENT: ..." line — the governor reads it and acts.
#
# NOTE: this script belongs to the governor. Role agents must not edit it —
# treat it as part of the protected scripts/ list in AGENTS.md.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DONE_TARGET=""
EXPECT_PENDING="__none__"
IGNORE_FAILED="__none__"
DRIVER_PATTERN=""
INTERVAL=5

while [ $# -gt 0 ]; do
  case "$1" in
    --done) DONE_TARGET="$2"; shift 2;;
    --expect-pending) EXPECT_PENDING="$2"; shift 2;;
    --ignore-failed) IGNORE_FAILED="$2"; shift 2;;
    --driver-pattern) DRIVER_PATTERN="$2"; shift 2;;
    --interval) INTERVAL="$2"; shift 2;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done

while true; do
  # 1) Unexpected pending task → pre-claim audit window
  NEWPEND="$(ls .queue/pending/ 2>/dev/null | grep -vE "$EXPECT_PENDING" | head -1)"
  if [ -n "$NEWPEND" ]; then
    echo "EVENT: NEW_PENDING $NEWPEND"
    exit 0
  fi
  # 2) New failure
  NEWFAIL="$(ls .queue/failed/ 2>/dev/null | grep -vE "$IGNORE_FAILED" | head -1)"
  if [ -n "$NEWFAIL" ]; then
    echo "EVENT: NEW_FAILED $NEWFAIL"
    exit 0
  fi
  # 3) Target done
  if [ -n "$DONE_TARGET" ] && ls .queue/done/ 2>/dev/null | grep -q "$DONE_TARGET"; then
    echo "EVENT: TARGET_DONE $DONE_TARGET"
    exit 0
  fi
  # 4) Driver death
  if [ -n "$DRIVER_PATTERN" ] && ! pgrep -f "$DRIVER_PATTERN" >/dev/null 2>&1; then
    echo "EVENT: DRIVER_DEAD $DRIVER_PATTERN"
    exit 0
  fi
  sleep "$INTERVAL"
done
