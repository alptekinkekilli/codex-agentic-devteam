# codex-agentic-devteam

Codex-first, queue-first multi-agent development scaffold.

This repo gives any project a local dev team made of five headless Codex role
agents:

```text
architect -> coder -> reviewer -> tester -> ops
```

A human or supervising Codex session acts as **Governor**. The governor does not
blindly delegate understanding. It writes precise briefs, gates the architect
plan before coder execution, verifies every "done" claim independently, and owns
the queue/dashboard/tooling substrate.

## What Ships

- `AGENTS.md` — Codex-native operating rules.
- `GOVERNOR.md` — governor charter, gates, known pitfalls, and recovery patterns.
- `docs/governor-prompts.md` — copy-paste prompts for continuing reviewer/tester/ops safely.
- `docs/install.md` — macOS/Linux/Windows install commands and first Governor prompts.
- `agents/` — role charters for architect, coder, reviewer, tester, and ops.
- `scripts/` — queue lifecycle, Codex driver, dashboard generator/server, and token usage recorder.
- `docs/controls/` — model routing and role capability policy.
- `docs/checklists/pre-push.md` — local safety checklist.
- `public/` — read-only local dashboard UI.
- `.queue/` — pending, in-progress, done, failed, events, and archive directories.
- `.claude/skills/` — legacy portable skill docs retained for compatibility.

The dashboard is intentionally governor-owned. Role agents must not edit it.

## Requirements

- macOS/Linux shell
- Python 3.10+
- Git
- GitHub CLI if publishing your derived project
- Codex CLI authenticated locally

Check Codex:

```bash
codex --version
codex exec --help
```

On macOS Codex Desktop, the binary may exist even when `codex` is not on `PATH`:

```bash
/Applications/Codex.app/Contents/Resources/codex --version
```

`scripts/role-agent.sh` checks both locations before claiming a task.

## Quick Start

Clone or copy this scaffold into a project:

```bash
git clone https://github.com/alptekinkekilli/codex-agentic-devteam.git
cd codex-agentic-devteam
python3 scripts/control_check.py
```

Start the dashboard:

```bash
python3 scripts/serve_dashboard_preview.py --live
```

The server defaults to `http://127.0.0.1:8766/?live=1`. If `8766` is busy, it
uses the next available port.

For OS-specific install commands and the first Governor prompts, see
[`docs/install.md`](docs/install.md).

## Cookiecutter Install

Install Cookiecutter:

```bash
python3 -m pip install --user cookiecutter
```

Generate a scaffolded project:

```bash
cookiecutter gh:alptekinkekilli/codex-agentic-devteam \
  --directory cookiecutter/codex-agentic-devteam
```

You will be prompted for:

- `project_name`
- `project_slug`
- `repo_description`
- `github_owner`
- `default_dashboard_port`

Then enter the generated project and validate it:

```bash
cd <project_slug>
python3 scripts/control_check.py
python3 scripts/generate_dashboard_status.py
python3 scripts/serve_dashboard_preview.py --live
```

## Existing Project Install

For an existing project, copy the scaffold files into the project root. Do not
blindly overwrite existing files.

Check for conflicts first:

```bash
for p in AGENTS.md CLAUDE.md GOVERNOR.md agents scripts docs/controls \
  docs/checklists/pre-push.md public .claude/skills .queue; do
  [ -e "$p" ] && echo "EXISTS $p" || echo "ABSENT $p"
done
```

If no conflicts exist, copy the scaffold. If conflicts exist, merge manually and
run validation before starting agents.

## Governor Workflow

1. Governor diagnoses the current repo state.
2. Governor writes one precise architect task.
3. Architect produces a plan and may enqueue a coder follow-up.
4. Governor reads the plan and verifies the coder task before starting build.
5. Coder, reviewer, tester, and ops run through the queue.
6. Governor re-runs checks, audits diffs, and reports the real outcome.

Product work is loop-routed. Queue, dashboard, model routing, and driver fixes
are governor-direct.

## Starting A Loop

Plan phase:

```bash
bash scripts/loop.sh plan landing-page "Build the landing page hero and signup flow"
```

After the governor approves the architect plan:

```bash
bash scripts/loop.sh build landing-page
```

Check status:

```bash
bash scripts/loop.sh status landing-page
```

Stop drivers:

```bash
bash scripts/loop.sh stop landing-page
```

## Model Routing

Model policy lives in `docs/controls/model_routing.json`.

Default routing:

- Governor: `gpt-5.5`, high reasoning
- Architect: `gpt-5.4`, high reasoning
- Coder: `gpt-5.5`, medium reasoning
- Reviewer: `gpt-5.4`, high reasoning
- Tester: `gpt-5.4-mini`, low reasoning
- Ops: `gpt-5.4-mini`, low reasoning

`scripts/role-agent.sh` reads this file and runs:

```bash
codex exec --json --model <model> --config model_reasoning_effort="<effort>"
```

## Dashboard

The dashboard reads sanitized snapshots from `public/status/`.

Generate snapshots:

```bash
python3 scripts/generate_dashboard_status.py
```

Serve live:

```bash
python3 scripts/serve_dashboard_preview.py --live
```

Live mode regenerates snapshots on `/status/*.json` requests with a throttle.

Dashboard files are protected governor-owned tooling. Do not assign them to
role-agent tasks.

## Environment Secrets

Project-local `.env` is gitignored. `scripts/role-agent.sh` sources `.env`
before launching Codex so environment-only secrets can reach child processes.
The driver never prints secret values.

For Hugging Face image generation:

```bash
grep -Eq '^(export )?HF_TOKEN=.+' .env && echo "HF_TOKEN line exists"
python3 -c 'import os; print("HF_TOKEN in env:", bool(os.getenv("HF_TOKEN")))'
```

The second command only returns `True` after `.env` is loaded in the current
shell or by the role driver.

## Validation Gates

Always run:

```bash
python3 scripts/control_check.py
```

For dashboard/driver changes:

```bash
bash -n scripts/role-agent.sh scripts/loop.sh scripts/governor-watch.sh
python3 -m py_compile scripts/*.py
python3 scripts/generate_dashboard_status.py
```

Smoke-test Codex execution:

```bash
printf '%s\n' 'Respond with exactly: OK' \
  | RUST_LOG=error codex exec --json --ignore-user-config \
      --model gpt-5.4-mini \
      --config 'model_reasoning_effort="low"' \
      --skip-git-repo-check \
      --sandbox read-only \
      -
```

## Pitfalls Captured From Real Use

- The dashboard is not part of the minimal scaffold because role agents must not
  mutate the governor control surface.
- `codex exec --json` emits JSONL, not a single JSON object.
- macOS Codex Desktop may not put `codex` on `PATH`; use the app bundle fallback.
- Some local Codex plugin/MCP configs can add noisy warnings; the driver uses
  `RUST_LOG=error` and `--ignore-user-config` for cleaner headless logs.
- Non-git workspaces need `--skip-git-repo-check`.
- Dashboard generation should tolerate `source_commit: no-git`.
- Port `8765` is often occupied by another agentic dashboard; this scaffold
  defaults to `8766` and auto-finds the next free port.
- Follow-up task `model_tier` and `model_alias` must match
  `model_routing.json`.
- Implementation coder tasks must include real application paths in
  `allowed_paths`; `.queue/` alone means the governor must reconcile the task.
- `.env` lines are not visible to agents unless loaded into process environment.
- A task manually placed in `.queue/done/` is not valid; close with
  `complete_task.py`.
- Public dashboard snapshots are generated artifacts and should not be treated
  as source truth.

More details are in `GOVERNOR.md` and `docs/operating-pitfalls.md`.
Use `docs/governor-prompts.md` for continuation prompts after each role completes.

## Publishing A Derived Repo

For a generated project:

```bash
git init
git add -A
git commit -m "Initialize Codex agentic devteam scaffold"
gh repo create <owner>/<repo> --public --source=. --remote=origin --push
```

Use `--private` instead of `--public` for private scaffolds.

## License

MIT.
