#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from queue_lib import QueueError, now_iso, read_json, task_path, validate_task, write_json_atomic, write_ready_event


def main() -> int:
    parser = argparse.ArgumentParser(description="Add a task JSON file to .queue/pending/.")
    parser.add_argument("task_file", help="Path to a task JSON file")
    args = parser.parse_args()

    try:
        source = Path(args.task_file)
        data = read_json(source)
        data.setdefault("created_at", now_iso())
        data["status"] = "pending"
        validate_task(data)
        target = task_path("pending", data["id"])
        if target.exists():
            raise QueueError(f"Pending task already exists: {target}")
        write_json_atomic(target, data)
        event = write_ready_event(data, target)
    except QueueError as exc:
        print(f"error: {exc}")
        return 1

    print(f"enqueued: {target}")
    print(f"event: {event}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
