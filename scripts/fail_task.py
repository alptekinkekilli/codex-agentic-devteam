#!/usr/bin/env python3
from __future__ import annotations

import argparse

from queue_lib import QueueError, move_task, read_json, task_path, validate_task


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail an in-progress task and move it to .queue/failed/.")
    parser.add_argument("task_id", help="Task id without .json suffix")
    parser.add_argument("--reason", required=True, help="Reason the task failed or was blocked")
    parser.add_argument("--follow-up", action="append", default=[], help="Follow-up task or note. May be repeated.")
    parser.add_argument("--summary", required=True, help="Short completion summary (required by role_capabilities.json)")
    parser.add_argument("--changed-file", action="append", default=[], help="Changed file path. May be repeated.")
    parser.add_argument("--validation", action="append", default=[], help="Validation command or result. May be repeated.")
    args = parser.parse_args()

    try:
        source = task_path("in-progress", args.task_id)
        data = read_json(source)
        validate_task(data)
        data["result"] = {
            "reason": args.reason,
            "follow_up": args.follow_up,
            "summary": args.summary,
            "changed_files": args.changed_file,
            "validation": args.validation,
        }
        target = move_task("in-progress", "failed", args.task_id, data)
    except QueueError as exc:
        print(f"error: {exc}")
        return 1

    print(f"failed: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
