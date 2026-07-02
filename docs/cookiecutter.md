# Cookiecutter Setup

This repository includes a Cookiecutter template under:

```text
cookiecutter/codex-agentic-devteam
```

Install:

```bash
python3 -m pip install --user cookiecutter
```

Generate from GitHub:

```bash
cookiecutter gh:alptekinkekilli/codex-agentic-devteam \
  --directory cookiecutter/codex-agentic-devteam
```

Generate from a local clone:

```bash
cookiecutter ./cookiecutter/codex-agentic-devteam
```

After generation:

```bash
cd <project_slug>
python3 scripts/control_check.py
python3 scripts/generate_dashboard_status.py
python3 scripts/serve_dashboard_preview.py --live
```

The generated repo is Codex-first:

- `AGENTS.md` is the primary instruction layer.
- `GOVERNOR.md` defines the supervising role.
- Role drivers use `codex exec --json`.
- Dashboard tooling is governor-owned and protected from role agents.

Recommended first commit:

```bash
git init
git add -A
git commit -m "Initialize Codex agentic devteam scaffold"
```
