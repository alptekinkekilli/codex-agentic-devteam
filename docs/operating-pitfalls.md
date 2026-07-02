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
- On macOS, Codex Desktop may install the CLI at
  `/Applications/Codex.app/Contents/Resources/codex` without putting `codex`
  on `PATH`. The driver must resolve both locations before a task is claimed.
- `--json` emits JSONL events, not one JSON document.
- Parse `turn.completed` for usage and `item.completed` with
  `item.type == "agent_message"` for final text.
- Use `--skip-git-repo-check` when the scaffold is being tested before `git init`.
- Use `--ignore-user-config` and `RUST_LOG=error` in role drivers to keep personal
  plugin/MCP warnings out of agent logs.
- Use `--dangerously-bypass-approvals-and-sandbox` only inside the role driver,
  because tasks are already constrained by queue metadata, capability policy, and
  governor approval.
- Load project-local `.env` before launching role agents when a task needs
  environment-only secrets such as `HF_TOKEN`. The driver may source `.env`, but
  it must never print values.

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
- If an implementation task has `allowed_paths: [".queue/"]`, stop. That is a
  contract bug, not a coder failure. Reconcile the task before any driver claims
  it.
- If a failed coder enqueues a reviewer handoff for a blocked/non-implementation
  task, supersede that reviewer task before proceeding with a corrected coder
  task.

## Governor Watch Discipline

- Start `scripts/governor-watch.sh` before starting a role driver.
- After a driver/tooling fix, do not restart the whole build chain. Run the next
  pending role in isolation, audit the result, then continue.
- `loop.sh build <scope>` is valid after the driver is proven, but isolated
  role runs are safer when recovering from driver, PATH, model, or auth issues.

## Hugging Face Assets

- `.env` content is not automatically in process environment unless loaded by
  the shell or driver.
- Check only booleans, never values:
  `python3 -c 'import os; print("HF_TOKEN in env:", bool(os.getenv("HF_TOKEN")))'`.
- If `HF_TOKEN` is absent and the coder creates an SVG fallback, the governor
  must decide whether the fallback satisfies the product goal or whether to
  create a bounded HF asset follow-up.
- HF asset notes should include prompt, model, and output path, but never token
  values.

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
