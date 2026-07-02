# Operating Pitfalls

These lessons came from real scaffold integration and should be treated as
standing governor knowledge.

## Dashboard Ownership

The dashboard is a governor control surface, not role-agent work. It is omitted
from minimal scaffolds on purpose so agents cannot mutate the tool used to
observe and govern them.

If the dashboard is needed in a target repo, the governor installs it directly:

- `public/`
- `scripts/generate_dashboard_status.py`
- `scripts/serve_dashboard_preview.py`
- `scripts/record_tokens.py`
- `scripts/archive_tasks.py`

Then the governor protects those paths in `AGENTS.md` and
`docs/controls/role_capabilities.json`.

## Codex Driver Details

- Use `codex exec --json` for headless role agents.
- `--json` emits JSONL events, not one JSON document.
- Parse `turn.completed` for usage and `item.completed` with
  `item.type == "agent_message"` for final text.
- Use `--skip-git-repo-check` when the scaffold is being tested before `git init`.
- Use `--ignore-user-config` and `RUST_LOG=error` in role drivers to keep personal
  plugin/MCP warnings out of agent logs.
- Use `--dangerously-bypass-approvals-and-sandbox` only inside the role driver,
  because tasks are already constrained by queue metadata, capability policy, and
  governor approval.

## Model Routing

Keep `model_tier` and `model_alias` in every task aligned with
`docs/controls/model_routing.json`.

Known good defaults:

- Governor: `gpt-5.5`, high
- Architect: `gpt-5.4`, high
- Coder: `gpt-5.5`, medium
- Reviewer: `gpt-5.4`, high
- Tester: `gpt-5.4-mini`, low
- Ops: `gpt-5.4-mini`, low

If `loop.sh` seeds a task with stale aliases, `control_check.py` catches it.

## Queue Integrity

- Never hand-place task JSON into `.queue/done/`.
- Use `scripts/complete_task.py` and `scripts/fail_task.py`.
- A file in `.queue/done/` is not proof of completion; the JSON body must have
  `"status": "done"` and a valid `result`.
- Stop a role driver before manually editing a pending task that it could claim.
- ID collisions cause claim loops; check all queue directories before reusing an id.

## Dashboard Runtime

- Default dashboard port is `8766`; `8765` is commonly occupied by another
  agentic dashboard.
- `serve_dashboard_preview.py` auto-finds the next free port.
- `public/status/` is generated runtime output; do not treat it as source truth.
- `source_commit: no-git` is acceptable before a target repo is initialized.

## Publishing

Before publishing a scaffold repo:

- Add `.gitignore` entries for `.env`, Python caches, `.queue/metrics/`, and
  `public/status/`.
- Run `rg` for common secret patterns.
- Run `control_check.py`, dashboard generation, shell syntax checks, and Python
  compile checks.
- Keep generated dashboard snapshots out of the initial commit unless publishing
  a static demo intentionally.
