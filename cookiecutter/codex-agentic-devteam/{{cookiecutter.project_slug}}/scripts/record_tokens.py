#!/usr/bin/env python3
"""Read headless agent output from stdin, echo the final text, and append one
usage record to .queue/metrics/tokens.jsonl.

Supports Codex `exec --json` JSONL and the older Claude single-JSON shape.

Usage (piped):  ... | record_tokens.py <role> <model> <task_id> <completed_at_iso>

The metrics file is runtime-only (gitignored). The dashboard reads it to show live
per-agent token performance and a per-task token report.
"""
from __future__ import annotations

import json
import sys

from queue_lib import QUEUE


METRICS_FILE = QUEUE / "metrics" / "tokens.jsonl"


def _arg(index: int) -> str:
    return sys.argv[index] if len(sys.argv) > index else ""


def _int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _blank_record(role: str, model: str, task_id: str, completed_at: str) -> dict[str, object]:
    return {
        "task_id": task_id,
        "role": role,
        "model": model,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "reasoning_output_tokens": 0,
        "cost_usd": None,
        "duration_ms": None,
        "num_turns": None,
        "completed_at": completed_at,
    }


def _write_record(record: dict[str, object]) -> None:
    METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with METRICS_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def _parse_codex_jsonl(raw: str, role: str, model: str, task_id: str, completed_at: str) -> bool:
    record = _blank_record(role, model, task_id, completed_at)
    final_messages: list[str] = []
    parsed_any = False

    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except (ValueError, json.JSONDecodeError):
            continue
        if not isinstance(event, dict):
            continue
        event_type = event.get("type")
        if event_type not in {
            "thread.started",
            "turn.started",
            "turn.completed",
            "turn.failed",
            "item.started",
            "item.completed",
            "error",
        }:
            continue
        parsed_any = True
        if event_type == "item.completed":
            item = event.get("item")
            if isinstance(item, dict) and item.get("type") == "agent_message":
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    final_messages.append(text)
        if event_type == "turn.completed":
            usage = event.get("usage")
            if isinstance(usage, dict):
                record["input_tokens"] += _int(usage.get("input_tokens"))
                record["output_tokens"] += _int(usage.get("output_tokens"))
                record["cache_read_input_tokens"] += _int(usage.get("cached_input_tokens"))
                record["cache_creation_input_tokens"] += _int(usage.get("cache_creation_input_tokens"))
                record["reasoning_output_tokens"] += _int(usage.get("reasoning_output_tokens"))
                record["num_turns"] = _int(record.get("num_turns")) + 1

    if not parsed_any:
        return False

    if final_messages:
        sys.stdout.write(final_messages[-1].rstrip() + "\n")
    _write_record(record)
    return True


def main() -> int:
    role, model, task_id, completed_at = _arg(1), _arg(2), _arg(3), _arg(4)
    raw = sys.stdin.read()

    if _parse_codex_jsonl(raw, role, model, task_id, completed_at):
        return 0

    try:
        data = json.loads(raw)
    except (ValueError, json.JSONDecodeError):
        # Not JSON (e.g. an error message) — pass it through unchanged and stop.
        sys.stdout.write(raw)
        return 0

    # Echo the agent's final text so logs/terminals stay readable.
    sys.stdout.write(str(data.get("result", "")) + "\n")

    usage = data.get("usage") or {}
    record = _blank_record(role, model, task_id, completed_at)
    record.update(
        {
            "input_tokens": _int(usage.get("input_tokens")),
            "output_tokens": _int(usage.get("output_tokens")),
            "cache_read_input_tokens": _int(usage.get("cache_read_input_tokens")),
            "cache_creation_input_tokens": _int(usage.get("cache_creation_input_tokens")),
            "cost_usd": data.get("total_cost_usd"),
            "duration_ms": data.get("duration_ms"),
            "num_turns": data.get("num_turns"),
        }
    )
    _write_record(record)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
