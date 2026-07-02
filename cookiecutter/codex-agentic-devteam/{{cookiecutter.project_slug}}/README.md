# {{ cookiecutter.project_name }}

{{ cookiecutter.repo_description }}

This project includes the `codex-agentic-devteam` scaffold:

```text
architect -> coder -> reviewer -> tester -> ops
```

The human or supervising Codex session is the **Governor**.

## Start Here

Validate the scaffold:

```bash
python3 scripts/control_check.py
python3 scripts/generate_dashboard_status.py
```

Start the dashboard:

```bash
python3 scripts/serve_dashboard_preview.py --live --port {{ cookiecutter.default_dashboard_port }}
```

Then open the URL printed by the server.

## Governor Rules

- Read `AGENTS.md` and `GOVERNOR.md` before starting a loop.
- Diagnose first; write precise architect briefs.
- Approve the architect plan before starting coder work.
- Treat dashboard/queue/driver/config changes as governor-direct.
- Do not let role agents edit dashboard or driver files.

## Run A Loop

Plan:

```bash
bash scripts/loop.sh plan {{ cookiecutter.project_slug }} "Describe the first objective"
```

After governor approval:

```bash
bash scripts/loop.sh build {{ cookiecutter.project_slug }}
```

Status:

```bash
bash scripts/loop.sh status {{ cookiecutter.project_slug }}
```

Stop:

```bash
bash scripts/loop.sh stop {{ cookiecutter.project_slug }}
```

## Model Routing

Edit `docs/controls/model_routing.json` if you want different Codex models.

Default:

- Governor: `gpt-5.5`, high
- Architect: `gpt-5.4`, high
- Coder: `gpt-5.5`, medium
- Reviewer: `gpt-5.4`, high
- Tester: `gpt-5.4-mini`, low
- Ops: `gpt-5.4-mini`, low

## Publish

```bash
git init
git add -A
git commit -m "Initialize Codex agentic devteam scaffold"
gh repo create {{ cookiecutter.github_owner }}/{{ cookiecutter.project_slug }} --public --source=. --remote=origin --push
```
