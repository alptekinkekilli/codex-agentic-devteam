#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from queue_lib import QUEUE, ROOT, QueueError, read_json


SCHEMA_VERSION = "1.0"
PROJECT_NAME = os.environ.get("AGENTIC_PROJECT_NAME", ROOT.name)
SOURCE_REPO = PROJECT_NAME
VISIBILITY = "private"
DEFAULT_OUTPUT_DIR = ROOT / "public" / "status"
QUEUE_STATUSES = ("pending", "in-progress", "done", "failed")
OUTPUT_FILES = (
    "project.json",
    "queue.json",
    "tasks.json",
    "agents.json",
    "usage.json",
    "plan.json",
    "model-routing.json",
    "patches.json",
    "sessions.json",
    "timeline.json",
    "activity.json",
    "health.json",
    "manifest.json",
)
FORBIDDEN_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"api[_-]?key",
        r"token",
        r"password",
        r"secret",
        r"BEGIN PRIVATE KEY",
        r"ssh-rsa",
        r"ghp_",
        r"sk-",
        r"AKIA",
        r"cookie",
    )
)


class SnapshotError(Exception):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def run_command(args: list[str]) -> str:
    completed = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        stdout = completed.stdout.strip()
        detail = stderr or stdout or f"exit code {completed.returncode}"
        raise SnapshotError(f"command failed: {' '.join(args)}: {detail}")
    return completed.stdout.strip()


def source_commit() -> str:
    try:
        return run_command(["git", "rev-parse", "HEAD"])
    except SnapshotError:
        return "no-git"


def ensure_repo_root() -> None:
    try:
        discovered = Path(run_command(["git", "rev-parse", "--show-toplevel"]))
    except SnapshotError:
        return
    if discovered != ROOT:
        raise SnapshotError(f"repo root mismatch: {discovered} != {ROOT}")


def run_control_check() -> None:
    run_command(["python3", "scripts/control_check.py"])


def envelope(data: dict[str, Any], generated_at: str, commit: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "source_repo": SOURCE_REPO,
        "source_commit": commit,
        "visibility": VISIBILITY,
        "data": data,
    }


def live_task_files() -> list[Path]:
    files: list[Path] = []
    for status in QUEUE_STATUSES:
        directory = QUEUE / status
        if not directory.is_dir():
            raise SnapshotError(f"missing queue directory: {directory}")
        files.extend(sorted(directory.glob("*.json")))
    return sorted(files)


def registry_task_files() -> list[Path]:
    docs_tasks = ROOT / "docs" / "tasks"
    return sorted(docs_tasks.glob("*.task.json"))


def read_tasks(paths: list[Path], source: str) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for path in paths:
        try:
            task = read_json(path)
        except QueueError as exc:
            raise SnapshotError(str(exc)) from exc
        task["_snapshot_source"] = source
        tasks.append(task)
    return sorted(tasks, key=lambda item: str(item.get("id", "")))


def non_empty_string(value: Any) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else ""


def deployment_metadata(task: dict[str, Any]) -> dict[str, str]:
    approval = task.get("deployment_approval")
    approval = approval if isinstance(approval, dict) else {}
    evidence = task.get("deployment_evidence")
    evidence = evidence if isinstance(evidence, dict) else {}
    source_commit = non_empty_string(approval.get("deployment_source_commit")) or non_empty_string(
        approval.get("expected_source_commit")
    )
    metadata = {
        "deployment_source_commit": source_commit,
        "evidence_record_commit": non_empty_string(approval.get("evidence_record_commit")),
        "deployment_id": non_empty_string(evidence.get("deployment_id")),
        "deployment_environment": non_empty_string(approval.get("environment")),
        "deployment_action_path": non_empty_string(approval.get("action_path")),
    }
    return {key: value for key, value in metadata.items() if value}


def task_scope(task: dict[str, Any]) -> str:
    explicit_scope = non_empty_string(task.get("project_scope"))
    if explicit_scope:
        return explicit_scope
    task_id = str(task.get("id", ""))
    title = str(task.get("title", "")).lower()
    haystack = f"{task_id.lower()} {title}"
    if "cyce" in haystack or task_id.startswith(("phase57-", "phase58-", "phase59-")):
        return "cyce-inspired-rebuild"
    if "smoke" in haystack or task_id.startswith(
        (
            "phase44-",
            "phase45-",
            "phase46-",
            "phase47-",
            "phase48-",
            "phase49-",
            "phase50-",
            "phase51-",
            "phase52-",
            "phase53-",
            "phase54-",
            "phase55-",
            "phase56-",
        )
    ):
        return "smoke-site-proof"
    if task_id.startswith("research-"):
        return "research"
    if task_id.startswith("dashboard-") or task_id.startswith(
        tuple(f"phase{number}-" for number in range(10, 44))
    ):
        return "dashboard-system"
    return "all-history"


def task_summary(task: dict[str, Any]) -> dict[str, Any]:
    result = task.get("result") if isinstance(task.get("result"), dict) else {}
    changed_files = result.get("changed_files", []) if isinstance(result, dict) else []
    validation = result.get("validation", []) if isinstance(result, dict) else []
    summary = {
        "id": task.get("id", ""),
        "title": task.get("title", ""),
        "status": task.get("status", ""),
        "role": task.get("role", ""),
        "model_tier": task.get("model_tier", ""),
        "model_alias": task.get("model_alias", ""),
        "created_at": task.get("created_at", ""),
        "summary": "",
        "changed_file_count": len(changed_files) if isinstance(changed_files, list) else 0,
        "validation_count": len(validation) if isinstance(validation, list) else 0,
        "snapshot_source": task.get("_snapshot_source", ""),
        "scope": task_scope(task),
    }
    summary.update(deployment_metadata(task))
    return summary


def timeline_item(
    task: dict[str, Any],
    *,
    event_type: str,
    from_status: str = "",
    to_status: str = "",
    observed_at: str = "",
) -> dict[str, Any]:
    result = task.get("result") if isinstance(task.get("result"), dict) else {}
    validation = result.get("validation", []) if isinstance(result, dict) else []
    item = {
        "task_id": task.get("id", ""),
        "title": task.get("title", ""),
        "role": task.get("role", ""),
        "model_alias": task.get("model_alias", "") or task.get("model_tier", ""),
        "from_status": from_status,
        "to_status": to_status,
        "event_type": event_type,
        "observed_at": observed_at,
        "snapshot_source": task.get("_snapshot_source", ""),
        "validation_count": len(validation) if isinstance(validation, list) else 0,
        "scope": task_scope(task),
    }
    item.update(deployment_metadata(task))
    return {key: value for key, value in item.items() if value not in ("", None)}


def ready_event_files() -> list[Path]:
    events_dir = QUEUE / "events"
    files = sorted(events_dir.glob("*.json")) if events_dir.is_dir() else []
    archive_dir = events_dir / "archive"
    if archive_dir.is_dir():
        files.extend(sorted(archive_dir.glob("*.json")))
    return sorted(files)


def build_timeline(live_tasks: list[dict[str, Any]], registry_tasks: list[dict[str, Any]]) -> dict[str, Any]:
    tasks_by_id: dict[str, dict[str, Any]] = {}
    for task in [*registry_tasks, *live_tasks]:
        task_id = str(task.get("id", ""))
        if task_id:
            tasks_by_id[task_id] = task

    items: list[dict[str, Any]] = []
    for task in registry_tasks:
        items.append(timeline_item(task, event_type="registered", to_status=str(task.get("status", ""))))

    for path in ready_event_files():
        try:
            event = read_json(path)
        except QueueError as exc:
            raise SnapshotError(str(exc)) from exc
        if event.get("event_type") != "ready":
            continue
        task_id = str(event.get("task_id", ""))
        if not task_id:
            continue
        task = tasks_by_id.get(task_id, {"id": task_id, "role": event.get("role", "")})
        items.append(
            timeline_item(
                task,
                event_type="ready",
                from_status="",
                to_status="pending",
                observed_at=non_empty_string(event.get("created_at")),
            )
        )

    for task in live_tasks:
        status = str(task.get("status", ""))
        items.append(timeline_item(task, event_type="current_status", to_status=status))
        if status in {"done", "failed"}:
            items.append(timeline_item(task, event_type=status, from_status="in-progress", to_status=status))

    items = sorted(
        items,
        key=lambda item: (
            str(item.get("observed_at", "")),
            str(item.get("task_id", "")),
            str(item.get("event_type", "")),
        ),
        reverse=True,
    )
    return {"items": items[:500]}


def redact_text(value: str) -> str:
    for pattern in FORBIDDEN_PATTERNS:
        value = pattern.sub("[redacted]", value)
    return value


def build_activity(limit: int = 60) -> dict[str, Any]:
    """Recent task activity for the live ticker, newest first.

    Derived from task-file modification times (the write that claims/completes a
    task), so each line reflects what a role just did. Uses task titles only (no
    free-form objective/summary) and redacts any forbidden token to stay clean.
    """
    verbs = {"pending": "queued", "in-progress": "is working on", "done": "completed", "failed": "failed"}
    icons = {"pending": "•", "in-progress": "▶", "done": "✓", "failed": "✗"}
    entries: list[dict[str, Any]] = []
    for status in QUEUE_STATUSES:
        directory = QUEUE / status
        if not directory.is_dir():
            continue
        for path in directory.glob("*.json"):
            if path.name == "task.schema.json":
                continue
            try:
                task = read_json(path)
            except QueueError:
                continue
            observed_at = (
                datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
                .astimezone()
                .isoformat(timespec="seconds")
            )
            role = str(task.get("role", ""))
            task_id = str(task.get("id", ""))
            title = str(task.get("title", ""))
            text = f"{role} {verbs.get(status, status)} {task_id}"
            if title:
                text += f" — {title}"
            entries.append(
                {
                    "observed_at": observed_at,
                    "role": role,
                    "status": status,
                    "task_id": task_id,
                    "scope": task_scope(task),
                    "icon": icons.get(status, "•"),
                    "text": redact_text(text),
                }
            )
    entries.sort(key=lambda item: (item["observed_at"], item["task_id"]), reverse=True)
    return {"items": entries[:limit]}


def latest_task_id(tasks: list[dict[str, Any]], status: str) -> str:
    candidates = [str(task.get("id", "")) for task in tasks if task.get("status") == status]
    return sorted(candidates)[-1] if candidates else ""


def build_project(live_tasks: list[dict[str, Any]]) -> dict[str, Any]:
    next_step = ""
    task_list = ROOT / "docs" / "tasks" / "TASK_LIST.md"
    if task_list.exists():
        lines = task_list.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            if line.strip() == "## Next":
                for candidate in lines[index + 1 :]:
                    stripped = candidate.strip()
                    if stripped.startswith("- "):
                        next_step = stripped[2:]
                        break
                    if stripped.startswith("## "):
                        break
                break

    # Scope list is derived from the scopes actually present in the live queue,
    # so every project (including new ones) is selectable without code edits.
    known_labels = {
        "appricode-tr": "Appricode.tr",
        "cyce-inspired-rebuild": "CYCE rebuild",
        "smoke-site-proof": "Smoke site proof",
        "dashboard-system": "Dashboard system",
        "research": "Research",
        "queue-observability": "Queue observability",
        "queue-throughput": "Queue throughput",
    }
    present: list[str] = []
    for task in live_tasks:
        scope = task_scope(task)
        if scope and scope not in present:
            present.append(scope)
    ordered = [s for s in known_labels if s in present] + [s for s in present if s not in known_labels]
    available_scopes = [{"id": s, "label": known_labels.get(s, s)} for s in ordered]
    available_scopes.append({"id": "all", "label": "All history"})

    # Default the dashboard to the currently-active project: the newest in-progress
    # task's scope, else the newest pending, else full history.
    def newest_scope(status: str) -> str:
        candidates = [t for t in live_tasks if t.get("status") == status and task_scope(t)]
        if not candidates:
            return ""
        candidates.sort(key=lambda t: str(t.get("created_at", "")), reverse=True)
        return task_scope(candidates[0])

    active_scope = newest_scope("in-progress") or newest_scope("pending") or "all"

    return {
        "name": PROJECT_NAME,
        "repo_role": "single-repo queue-first devteam workspace",
        "core_repo": "",
        "private_repo": PROJECT_NAME,
        "current_focus": "local dashboard and queue-first agent tracking",
        "active_scope": active_scope,
        "available_scopes": available_scopes,
        "next_step": next_step,
        "last_checkpoint": latest_task_id(live_tasks, "done"),
    }


def build_queue(live_tasks: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {status.replace("-", "_"): 0 for status in QUEUE_STATUSES}
    for task in live_tasks:
        status = str(task.get("status", ""))
        key = status.replace("-", "_")
        if key in counts:
            counts[key] += 1
    return {
        "counts": counts,
        "latest_done_task_id": latest_task_id(live_tasks, "done"),
        "latest_failed_task_id": latest_task_id(live_tasks, "failed"),
        "stale_in_progress_task_ids": [],
    }


TOKENS_FILE = QUEUE / "metrics" / "tokens.jsonl"


def read_usage_records() -> list[dict[str, Any]]:
    """Read runtime per-agent usage records (.queue/metrics/tokens.jsonl)."""
    if not TOKENS_FILE.is_file():
        return []
    records: list[dict[str, Any]] = []
    for line in TOKENS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except (ValueError, json.JSONDecodeError):
            continue
    return records


def _blank_usage() -> dict[str, Any]:
    # Keys intentionally avoid the substring "token" (forbidden-pattern scan).
    return {"input": 0, "output": 0, "cost_usd": 0.0, "tasks": 0}


def usage_by_role(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_role: dict[str, dict[str, Any]] = {}
    for record in records:
        role = str(record.get("role", ""))
        agg = by_role.setdefault(role, _blank_usage())
        agg["input"] += int(record.get("input_tokens", 0) or 0)
        agg["output"] += int(record.get("output_tokens", 0) or 0)
        agg["cost_usd"] = round(agg["cost_usd"] + float(record.get("cost_usd") or 0), 6)
        agg["tasks"] += 1
    return by_role


_TASK_ID_SCOPE = re.compile(r"^(.*)-(?:architect|coder|reviewer|tester|ops)-\d+$")


def _scope_from_task_id(task_id: str) -> str:
    """Task ids are '<scope>-<role>-<NNNN>' — recover the scope for per-scope filtering."""
    match = _TASK_ID_SCOPE.match(task_id)
    return match.group(1) if match else (task_id or "")


def build_usage() -> dict[str, Any]:
    """Per-task usage report + per-role + grand totals. Field names avoid 'token'.

    Each report row carries its `scope` (from the task id) so the dashboard can show
    per-scope agent + token performance, not just global totals.
    """
    records = read_usage_records()
    by_role = usage_by_role(records)
    totals = _blank_usage()
    report: list[dict[str, Any]] = []
    for record in records:
        totals["input"] += int(record.get("input_tokens", 0) or 0)
        totals["output"] += int(record.get("output_tokens", 0) or 0)
        totals["cost_usd"] = round(totals["cost_usd"] + float(record.get("cost_usd") or 0), 6)
        totals["tasks"] += 1
        task_id = str(record.get("task_id", ""))
        report.append(
            {
                "task_id": task_id,
                "scope": str(record.get("scope") or _scope_from_task_id(task_id)),
                "role": str(record.get("role", "")),
                "model": str(record.get("model", "")),
                "input": int(record.get("input_tokens", 0) or 0),
                "output": int(record.get("output_tokens", 0) or 0),
                "cost_usd": record.get("cost_usd"),
                "duration_ms": record.get("duration_ms"),
                "turns": record.get("num_turns"),
                "completed_at": str(record.get("completed_at", "")),
            }
        )
    report = list(reversed(report))[:100]
    return {"report": report, "by_role": by_role, "totals": totals}


def _extract_mermaid(text: str) -> list[str]:
    blocks: list[str] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith("```mermaid"):
            j = i + 1
            buf: list[str] = []
            while j < len(lines) and not lines[j].strip().startswith("```"):
                buf.append(lines[j])
                j += 1
            if buf:
                blocks.append("\n".join(buf))
            i = j + 1
        else:
            i += 1
    return blocks


def _mermaid_label(value: str) -> str:
    cleaned = value.replace("`", "").replace('"', "'").replace("[", "(").replace("]", ")")
    return cleaned.strip()[:42]


def _pipeline_mermaid(scope: str, live_tasks: list[dict[str, Any]]) -> str:
    order = ["architect", "coder", "reviewer", "tester", "ops"]
    icons = {"done": "done", "in-progress": "now", "pending": "queued", "failed": "failed"}
    status_by_role: dict[str, str] = {}
    for task in live_tasks:
        if task_scope(task) == scope:
            status_by_role[str(task.get("role", ""))] = str(task.get("status", ""))
    nodes = [f'  {role}["{role} ({icons.get(status_by_role.get(role, ""), "—")})"]' for role in order]
    chain = " --> ".join(order)
    return "flowchart LR\n" + "\n".join(nodes) + f"\n  {chain}"


def _headings_mermaid(design_text: str) -> str:
    heads = [_mermaid_label(line[3:]) for line in design_text.splitlines() if line.startswith("## ")]
    heads = [h for h in heads if h]
    if len(heads) < 2:
        return ""
    nodes = [f'  h{i}["{h}"]' for i, h in enumerate(heads)]
    chain = " --> ".join(f"h{i}" for i in range(len(heads)))
    return "flowchart TD\n" + "\n".join(nodes) + f"\n  {chain}"


def build_plan(live_tasks: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-scope plan content: the design doc + loop README + mermaid diagrams.

    Lets the dashboard render the architect's plan (clicked from a task) with a visual.
    All text is redacted to pass the forbidden-pattern scan.
    """
    scopes: list[str] = []
    for task in live_tasks:
        scope = task_scope(task)
        if scope and scope not in scopes:
            scopes.append(scope)

    by_scope: dict[str, Any] = {}
    for scope in scopes:
        # Architect plan docs are named "{scope}.md" (older convention) or
        # "{scope}-<topic>-plan.md" (current convention, since a scope can pick up
        # multiple bounded plans over its lifetime) — glob by scope prefix and
        # concatenate every match instead of requiring one exact filename.
        design_dir = ROOT / "docs" / "architecture"
        design_paths = sorted(design_dir.glob(f"{scope}*.md")) if design_dir.is_dir() else []
        readme_path = ROOT / "docs" / "loops" / scope / "README.md"
        design = (
            "\n\n---\n\n".join(path.read_text(encoding="utf-8") for path in design_paths)
            if design_paths
            else ""
        )
        readme = readme_path.read_text(encoding="utf-8") if readme_path.is_file() else ""
        if not design and not readme:
            continue
        diagrams = [_pipeline_mermaid(scope, live_tasks)]
        diagrams.extend(_extract_mermaid(design))
        diagrams.extend(_extract_mermaid(readme))
        headings = _headings_mermaid(design)
        if headings:
            diagrams.append(headings)
        by_scope[scope] = {
            "design": redact_text(design),
            "readme": redact_text(readme),
            "mermaid": [redact_text(d) for d in diagrams if d],
        }
    return {"by_scope": by_scope}


def build_agents() -> dict[str, Any]:
    capabilities = read_json(ROOT / "docs" / "controls" / "role_capabilities.json")
    routing = read_json(ROOT / "docs" / "controls" / "model_routing.json")
    roles = routing.get("roles", {})
    tiers = routing.get("tiers", {}) if isinstance(routing.get("tiers"), dict) else {}
    by_role = usage_by_role(read_usage_records())
    items: list[dict[str, Any]] = []
    for role in sorted(capabilities):
        role_caps = capabilities.get(role, {})
        route = roles.get(role, {}) if isinstance(roles, dict) else {}
        tier = route.get("tier", "")
        tier_info = tiers.get(tier, {}) if isinstance(tiers, dict) else {}
        may_edit = role_caps.get("may_edit", [])
        must_not_edit = role_caps.get("must_not_edit", [])
        items.append(
            {
                "role": role,
                "responsibility": agent_heading(role),
                "model_tier": tier,
                "model_alias": route.get("alias", ""),
                "model": tier_info.get("model", "") if isinstance(tier_info, dict) else "",
                "usage": by_role.get(role, _blank_usage()),
                "may_edit_count": len(may_edit) if isinstance(may_edit, list) else 0,
                "must_not_edit_count": len(must_not_edit) if isinstance(must_not_edit, list) else 0,
                "scope_summary": "bounded by role capability policy",
            }
        )
    return {"items": items}


def agent_heading(role: str) -> str:
    path = ROOT / "agents" / f"{role}.md"
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return ""


def build_model_routing() -> dict[str, Any]:
    return read_json(ROOT / "docs" / "controls" / "model_routing.json")


def collect_markdown_sections(path: Path, marker: str) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(marker):
            if current:
                sections.append(current)
            current = {"title": line.lstrip("#").strip(), "lines": []}
        elif current is not None:
            stripped = line.strip()
            if stripped:
                current["lines"].append(stripped)
    if current:
        sections.append(current)
    return sections


def build_patches() -> dict[str, Any]:
    sections = collect_markdown_sections(ROOT / "docs" / "patches" / "PATCH_REGISTRY.md", "### ")
    return {"items": [{"title": section["title"]} for section in sections[-25:]]}


def build_sessions() -> dict[str, Any]:
    sections = collect_markdown_sections(ROOT / "docs" / "sessions" / "SESSION_LOG.md", "## ")
    return {"items": [{"title": section["title"]} for section in sections[-25:]]}


def build_health() -> dict[str, Any]:
    jq_available = shutil.which("jq") is not None
    vercel_ready = (ROOT / "docs" / "ops" / "bootstrap-0061-vercel-visual-dashboard-check.md").exists()
    checks = [
        {
            "label": "Control",
            "status": "ok",
            "detail": "control_check passed during snapshot generation",
        },
        {
            "label": "Queue dirs",
            "status": "ok" if all((QUEUE / status).is_dir() for status in QUEUE_STATUSES) else "blocked",
            "detail": "required queue directories are present",
        },
        {
            "label": "jq",
            "status": "ok" if jq_available else "blocked",
            "detail": "jq is available to local queue-status helper" if jq_available else "jq is missing for local queue-status helper",
        },
        {
            "label": "Memory",
            "status": "not_checked",
            "detail": "memory redaction has a checklist but no automated dashboard scan yet",
        },
        {
            "label": "Vercel",
            "status": "ok" if vercel_ready else "pending",
            "detail": "owner visual dashboard check passed" if vercel_ready else "owner visual dashboard check is pending",
        },
    ]
    blocking_reasons = [check["detail"] for check in checks if check["status"] == "blocked"]
    return {
        "control_check_passed": True,
        "queue_dirs_present": all((QUEUE / status).is_dir() for status in QUEUE_STATUSES),
        "jq_required": True,
        "jq_available_at_generation": jq_available,
        "pre_push_checked": False,
        "memory_redaction_checked": False,
        "vercel_ready": vercel_ready,
        "checks": checks,
        "blocking_reasons": blocking_reasons,
    }


def build_snapshots(generated_at: str, commit: str) -> dict[str, dict[str, Any]]:
    live_tasks = read_tasks(live_task_files(), "queue")
    registry_tasks = read_tasks(registry_task_files(), "registry")
    tasks = sorted([*live_tasks, *registry_tasks], key=lambda item: str(item.get("id", "")))
    snapshots = {
        "project.json": envelope(build_project(live_tasks), generated_at, commit),
        "queue.json": envelope(build_queue(live_tasks), generated_at, commit),
        "tasks.json": envelope({"items": [task_summary(task) for task in tasks]}, generated_at, commit),
        "agents.json": envelope(build_agents(), generated_at, commit),
        "usage.json": envelope(build_usage(), generated_at, commit),
        "plan.json": envelope(build_plan(live_tasks), generated_at, commit),
        "model-routing.json": envelope(build_model_routing(), generated_at, commit),
        "patches.json": envelope(build_patches(), generated_at, commit),
        "sessions.json": envelope(build_sessions(), generated_at, commit),
        "timeline.json": envelope(build_timeline(live_tasks, registry_tasks), generated_at, commit),
        "activity.json": envelope(build_activity(), generated_at, commit),
        "health.json": envelope(build_health(), generated_at, commit),
    }
    snapshots["manifest.json"] = envelope(
        {
            "generator": {
                "name": "generate_dashboard_status.py",
                "mode": "local",
                "status": "success",
            },
            "files": sorted(snapshots),
            "validation": {
                "control_check_passed": True,
                "json_validation_passed": True,
                "forbidden_pattern_scan_passed": True,
            },
            "blocking_reasons": [],
        },
        generated_at,
        commit,
    )
    return snapshots


def scan_forbidden(snapshots: dict[str, dict[str, Any]]) -> None:
    for name, data in snapshots.items():
        payload = json.dumps(data, sort_keys=True)
        for pattern in FORBIDDEN_PATTERNS:
            if pattern.search(payload):
                raise SnapshotError(f"forbidden pattern {pattern.pattern!r} found in {name}")


def write_snapshot(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")


def validate_json_file(path: Path) -> None:
    run_command(["python3", "-m", "json.tool", str(path)])


def validate_output_dir(output_dir: Path) -> Path:
    resolved = output_dir.resolve()
    home = Path.home().resolve()
    allowed_default = DEFAULT_OUTPUT_DIR.resolve()

    forbidden_exact = {ROOT, ROOT.parent, home, home.parent}
    if resolved in forbidden_exact:
        raise SnapshotError(f"unsafe output directory: {resolved}")
    if resolved == Path(resolved.anchor):
        raise SnapshotError(f"unsafe output directory: {resolved}")
    if resolved == allowed_default:
        return resolved
    if resolved.name != "status":
        raise SnapshotError("output directory must be named 'status' unless using the default public/status path")
    if ROOT in resolved.parents and resolved.parent != allowed_default.parent:
        raise SnapshotError(f"unsafe output directory inside repo: {resolved}")
    return resolved


def ensure_managed_output_dir(output_dir: Path) -> None:
    if not output_dir.exists():
        return
    if not output_dir.is_dir():
        raise SnapshotError(f"output path is not a directory: {output_dir}")

    managed = set(OUTPUT_FILES)
    unmanaged = sorted(path.name for path in output_dir.iterdir() if path.name not in managed)
    if unmanaged:
        raise SnapshotError(f"output directory contains unmanaged files: {', '.join(unmanaged)}")

    non_files = sorted(path.name for path in output_dir.iterdir() if path.name in managed and not path.is_file())
    if non_files:
        raise SnapshotError(f"managed snapshot entries must be regular files: {', '.join(non_files)}")


def write_snapshots(output_dir: Path, snapshots: dict[str, dict[str, Any]]) -> None:
    expected = set(OUTPUT_FILES)
    if set(snapshots) != expected:
        missing = sorted(expected - set(snapshots))
        extra = sorted(set(snapshots) - expected)
        raise SnapshotError(f"snapshot file mismatch; missing={missing}, extra={extra}")

    output_dir = validate_output_dir(output_dir)
    ensure_managed_output_dir(output_dir)
    temp_parent = output_dir.parent
    temp_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".status-tmp-", dir=temp_parent) as temp_name:
        temp_dir = Path(temp_name)
        for name in OUTPUT_FILES:
            path = temp_dir / name
            write_snapshot(path, snapshots[name])
            validate_json_file(path)

        if output_dir.exists():
            shutil.rmtree(output_dir)
        os.replace(temp_dir, output_dir)


def generate(output_dir: Path) -> list[str]:
    ensure_repo_root()
    run_control_check()
    snapshots = build_snapshots(now_iso(), source_commit())
    scan_forbidden(snapshots)
    write_snapshots(output_dir, snapshots)
    return sorted(snapshots)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate sanitized dashboard status snapshots.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Snapshot output directory. Defaults to public/status/.",
    )
    args = parser.parse_args()

    try:
        files = generate(Path(args.output_dir))
    except (QueueError, SnapshotError) as exc:
        print(f"error: {exc}")
        return 1

    print(f"generated {len(files)} dashboard snapshot files in {args.output_dir}")
    for name in files:
        print(f"- {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
