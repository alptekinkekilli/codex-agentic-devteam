#!/usr/bin/env python3
"""Archive completed tasks out of .queue/done/ into .queue/archive/done/.

Read-write helper used by the local dashboard's archive endpoint and from the CLI.
Safe by construction: ids are validated (no path traversal), only files that exist
directly in .queue/done/ are moved, nothing is deleted, and the move is atomic.
"""
from __future__ import annotations

import argparse
from typing import Any

from queue_lib import QUEUE, QueueError, safe_queue_id


ARCHIVE_DONE = QUEUE / "archive" / "done"


def archive_tasks(task_ids: list[str]) -> dict[str, Any]:
    """Move .queue/done/<id>.json -> .queue/archive/done/<id>.json for each id.

    Returns {"archived": [ids], "skipped": [{"id", "reason"}]}.
    """
    ARCHIVE_DONE.mkdir(parents=True, exist_ok=True)
    archived: list[str] = []
    skipped: list[dict[str, str]] = []

    for raw in task_ids:
        try:
            task_id = safe_queue_id(str(raw), "task id")
        except QueueError:
            skipped.append({"id": str(raw), "reason": "invalid id"})
            continue

        source = QUEUE / "done" / f"{task_id}.json"
        if not source.is_file():
            skipped.append({"id": task_id, "reason": "not in .queue/done"})
            continue

        target = ARCHIVE_DONE / f"{task_id}.json"
        if target.exists():
            skipped.append({"id": task_id, "reason": "already archived"})
            continue

        source.replace(target)
        archived.append(task_id)

    return {"archived": archived, "skipped": skipped}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Archive completed tasks out of .queue/done/ into .queue/archive/done/."
    )
    parser.add_argument("task_ids", nargs="+", help="Task ids (without .json) to archive")
    args = parser.parse_args()

    result = archive_tasks(args.task_ids)
    for task_id in result["archived"]:
        print(f"archived: {task_id}")
    for entry in result["skipped"]:
        print(f"skipped: {entry['id']} ({entry['reason']})")

    return 0 if result["archived"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
