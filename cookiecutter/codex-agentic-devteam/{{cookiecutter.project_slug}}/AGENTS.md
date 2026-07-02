# AGENTS.md

## Project Purpose

This repository is `{{ cookiecutter.project_name }}`: {{ cookiecutter.repo_description }}.

It includes a Codex-first, queue-first multi-agent development scaffold.
It gives a project five bounded worker roles:

- architect
- coder
- reviewer
- tester
- ops

The human or supervising Codex session acts as **Governor**. The governor writes
briefs, approves plans, verifies claims, and owns the scaffold tooling.

## Operating Model

- Product or application work goes through the queue:
  architect -> coder -> reviewer -> tester -> ops.
- The governor must approve the architect plan before coder execution starts.
- Queue/tooling/dashboard/config fixes are **governor-direct** work and must not
  be routed to role agents.
- Role agents claim exactly one task at a time from `.queue/pending/`.
- Role agents close tasks only through `scripts/complete_task.py` or
  `scripts/fail_task.py`.

## Dashboard Ownership

The dashboard is a governor-owned control surface.

Role agents must not edit:

- `public/*`
- `scripts/archive_tasks.py`
- `scripts/generate_dashboard_status.py`
- `scripts/record_tokens.py`
- `scripts/serve_dashboard_preview.py`
- `scripts/role-agent.sh`
- `scripts/loop.sh`
- `docs/controls/model_routing.json`
- `docs/controls/role_capabilities.json`

If the dashboard, driver, queue, or model routing breaks, the governor fixes it
directly, runs validation, and records what changed.

## Codex Driver

The role driver is `scripts/role-agent.sh`.

It runs headless agents through:

```bash
codex exec --json
```

The driver resolves Codex from `PATH` first, then from the macOS Codex Desktop
fallback path `/Applications/Codex.app/Contents/Resources/codex`. It loads a
project-local `.env` for child processes without printing values.

Model and reasoning choices come from `docs/controls/model_routing.json`.

Default routing:

- Governor: `gpt-5.5`, high reasoning
- Architect: `gpt-5.4`, high reasoning
- Coder: `gpt-5.5`, medium reasoning
- Reviewer: `gpt-5.4`, high reasoning
- Tester: `gpt-5.4-mini`, low reasoning
- Ops: `gpt-5.4-mini`, low reasoning

## Validation

Run after every queue/control/dashboard/driver change:

```bash
python3 scripts/control_check.py
python3 scripts/generate_dashboard_status.py
```

For shell/Python driver changes, also run:

```bash
bash -n scripts/role-agent.sh scripts/loop.sh scripts/governor-watch.sh
python3 -m py_compile scripts/*.py
```

## Safety

- No secrets in task files, dashboard snapshots, logs, commits, or chat.
- No push, PR, deploy, DNS, provider API, or irreversible operation from role agents.
- The governor may publish only after explicit human instruction.
- Do not rewrite another actor's commits.
- Do not use destructive git commands unless explicitly requested.
