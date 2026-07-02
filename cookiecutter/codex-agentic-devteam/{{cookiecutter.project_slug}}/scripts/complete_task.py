#!/usr/bin/env python3
from __future__ import annotations

import argparse

from queue_lib import QueueError, move_task, read_json, task_path, validate_task, write_json_atomic


def main() -> int:
    parser = argparse.ArgumentParser(description="Complete an in-progress task and move it to .queue/done/.")
    parser.add_argument("task_id", help="Task id without .json suffix")
    parser.add_argument("--summary", required=True, help="Short completion summary")
    parser.add_argument("--changed-file", action="append", default=[], help="Changed file path. May be repeated.")
    parser.add_argument("--validation", action="append", default=[], help="Validation command or result. May be repeated.")
    args = parser.parse_args()

    try:
        in_progress = task_path("in-progress", args.task_id)
        done = task_path("done", args.task_id)

        if done.exists():
            # Idempotent path: preserve the authoritative done record verbatim.
            # Self-heal any stale in-progress ghost copy so the dashboard stays clean.
            ghost_removed = False
            if in_progress.exists():
                in_progress.unlink()
                ghost_removed = True

            # Self-heal a done/ file that was placed there without going through this
            # script (e.g. a raw file move) and still carries in-progress semantics:
            # status != "done" and/or no result payload. The dashboard reads the
            # internal status field, so a mismatch here renders as a stuck card.
            done_data = read_json(done)
            if done_data.get("status") != "done" or "result" not in done_data:
                done_data["status"] = "done"
                done_data.setdefault(
                    "result",
                    {
                        "summary": args.summary,
                        "changed_files": args.changed_file,
                        "validation": args.validation,
                    },
                )
                write_json_atomic(done, done_data)
                print(f"completed (self-healed done record with stale internal status): {done}")
            elif ghost_removed:
                print(f"completed (already done, stale in-progress removed): {done}")
            else:
                print(f"completed (already done, no ghost): {done}")
            return 0

        source = in_progress
        data = read_json(source)
        validate_task(data)
        data["result"] = {
            "summary": args.summary,
            "changed_files": args.changed_file,
            "validation": args.validation,
        }
        target = move_task("in-progress", "done", args.task_id, data)
    except QueueError as exc:
        print(f"error: {exc}")
        return 1

    print(f"completed: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
