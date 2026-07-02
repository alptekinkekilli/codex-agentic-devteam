#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from queue_lib import ROOT, QUEUE, QueueError, read_json, validate_task


CAPABILITIES_PATH = ROOT / "docs" / "controls" / "role_capabilities.json"
MODEL_ROUTING_PATH = ROOT / "docs" / "controls" / "model_routing.json"
TASK_DIRS = [
    QUEUE / "pending",
    QUEUE / "in-progress",
    QUEUE / "done",
    QUEUE / "failed",
    ROOT / "docs" / "tasks",
]


def load_capabilities() -> dict[str, Any]:
    data = read_json(CAPABILITIES_PATH)
    if not isinstance(data, dict):
        raise QueueError("Role capabilities must be a JSON object")
    return data


def load_model_routing() -> dict[str, Any]:
    data = read_json(MODEL_ROUTING_PATH)
    if not isinstance(data, dict):
        raise QueueError("Model routing must be a JSON object")
    return data


def normalize_prefix(path: str) -> str:
    return path.rstrip("/") + ("/" if path.endswith("/") else "")


def path_allowed(path: str, prefixes: list[str]) -> bool:
    normalized = normalize_prefix(path)
    for prefix in prefixes:
        allowed = normalize_prefix(prefix)
        if normalized == allowed or normalized.startswith(allowed):
            return True
    return False


def overlaps_forbidden(path: str, prefixes: list[str]) -> bool:
    normalized = normalize_prefix(path)
    for prefix in prefixes:
        forbidden = normalize_prefix(prefix)
        if normalized == forbidden or normalized.startswith(forbidden) or forbidden.startswith(normalized):
            return True
    return False


def validate_capabilities(task: dict[str, Any], capabilities: dict[str, Any], source: Path) -> list[str]:
    errors: list[str] = []
    role = task["role"]
    role_caps = capabilities.get(role)
    if not isinstance(role_caps, dict):
        return [f"{source}: missing capabilities for role {role}"]

    may_edit = role_caps.get("may_edit", [])
    must_not_edit = role_caps.get("must_not_edit", [])
    if not isinstance(may_edit, list) or not isinstance(must_not_edit, list):
        return [f"{source}: role capabilities must use list values"]

    for allowed_path in task["allowed_paths"]:
        if not path_allowed(allowed_path, may_edit):
            errors.append(f"{source}: {role} cannot edit allowed path {allowed_path}")
        if overlaps_forbidden(allowed_path, must_not_edit):
            errors.append(f"{source}: {role} allowed path overlaps forbidden path {allowed_path}")

    if task["status"] in {"done", "failed"}:
        result = task.get("result")
        if not isinstance(result, dict):
            errors.append(f"{source}: completed task must include result object")
        else:
            required = role_caps.get("required_completion_fields", [])
            for field in required:
                if field not in result:
                    errors.append(f"{source}: result missing required field {field}")

    return errors


def validate_model_routing_config(routing: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    tiers = routing.get("tiers")
    roles = routing.get("roles")
    guardrails = routing.get("budget_guardrails", {})

    if not isinstance(tiers, dict):
        return ["model routing: tiers must be an object"]
    if not isinstance(roles, dict):
        return ["model routing: roles must be an object"]

    premium_allowed = guardrails.get("premium_allowed_roles", [])
    if not isinstance(premium_allowed, list):
        errors.append("model routing: premium_allowed_roles must be a list")
        premium_allowed = []

    for role in ("architect", "coder", "reviewer", "tester", "ops"):
        route = roles.get(role)
        if not isinstance(route, dict):
            errors.append(f"model routing: missing route for {role}")
            continue

        tier = route.get("tier")
        alias = route.get("alias")
        reason = route.get("reason")
        if tier not in tiers:
            errors.append(f"model routing: {role} references unknown tier {tier}")
        if not isinstance(alias, str) or not alias:
            errors.append(f"model routing: {role} must define alias")
        if not isinstance(reason, str) or not reason:
            errors.append(f"model routing: {role} must define reason")
        if tier == "premium" and role not in premium_allowed:
            errors.append(f"model routing: premium tier is not allowed for {role}")

    return errors


def validate_task_model_route(task: dict[str, Any], routing: dict[str, Any], source: Path) -> list[str]:
    errors: list[str] = []
    route = routing.get("roles", {}).get(task["role"], {})
    if not isinstance(route, dict):
        return [f"{source}: missing model route for role {task['role']}"]

    task_tier = task.get("model_tier")
    task_alias = task.get("model_alias")
    if task_tier is not None and task_tier != route.get("tier"):
        errors.append(f"{source}: model_tier {task_tier} does not match role tier {route.get('tier')}")
    if task_alias is not None and task_alias != route.get("alias"):
        errors.append(f"{source}: model_alias {task_alias} does not match role alias {route.get('alias')}")
    return errors


def iter_task_files() -> list[Path]:
    files: list[Path] = []
    for task_dir in TASK_DIRS:
        if task_dir.exists():
            files.extend(path for path in task_dir.glob("*.json") if path.name != "task.schema.json")
    return sorted(files)


def main() -> int:
    errors: list[str] = []
    try:
        capabilities = load_capabilities()
        model_routing = load_model_routing()
    except QueueError as exc:
        print(f"error: {exc}")
        return 1

    errors.extend(validate_model_routing_config(model_routing))

    for path in iter_task_files():
        try:
            task = read_json(path)
            validate_task(task)
            errors.extend(validate_capabilities(task, capabilities, path))
            errors.extend(validate_task_model_route(task, model_routing, path))
        except QueueError as exc:
            errors.append(f"{path}: {exc}")

    if errors:
        for error in errors:
            print(f"error: {error}")
        return 1

    print(f"control check passed: {len(iter_task_files())} task files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
