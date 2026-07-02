# Install And First Governor Prompts

This guide covers two paths:

- Generate a new project from the Cookiecutter template.
- Add the scaffold to an existing project.

The scaffold uses Bash role drivers. On Windows, WSL or Git Bash is recommended
for running `scripts/*.sh`.

## macOS / Linux: New Project

```bash
python3 -m pip install --user cookiecutter

cookiecutter gh:alptekinkekilli/codex-agentic-devteam \
  --directory cookiecutter/codex-agentic-devteam

cd <project_slug>

python3 scripts/control_check.py
python3 scripts/generate_dashboard_status.py
python3 scripts/serve_dashboard_preview.py --live
```

Check Codex:

```bash
codex --version || /Applications/Codex.app/Contents/Resources/codex --version
```

## macOS / Linux: Existing Project

Run these commands from the existing project root.

```bash
git clone --depth 1 https://github.com/alptekinkekilli/codex-agentic-devteam.git /tmp/codex-agentic-devteam
```

Check for conflicts before copying:

```bash
for p in AGENTS.md CLAUDE.md GOVERNOR.md agents scripts docs/controls \
  docs/checklists/pre-push.md public .claude/skills .queue; do
  [ -e "$p" ] && echo "EXISTS $p" || echo "ABSENT $p"
done
```

If every required path is `ABSENT`, copy the scaffold:

```bash
rsync -a \
  --exclude '.git' \
  --exclude 'cookiecutter' \
  --exclude 'public/status' \
  --exclude '.queue/metrics' \
  /tmp/codex-agentic-devteam/ ./

rm -rf /tmp/codex-agentic-devteam

python3 scripts/control_check.py
python3 scripts/generate_dashboard_status.py
python3 scripts/serve_dashboard_preview.py --live
```

If any path reports `EXISTS`, do not copy blindly. Merge manually or ask a
Governor session to reconcile the conflicts.

## Windows: Recommended Environment

Use WSL Ubuntu, recommended, or Git Bash. PowerShell can clone and copy files,
but the role drivers are Bash scripts. Use WSL/Git Bash for:

- `scripts/role-agent.sh`
- `scripts/loop.sh`
- `scripts/governor-watch.sh`

## Windows / WSL: New Project

```bash
python3 -m pip install --user cookiecutter

cookiecutter gh:alptekinkekilli/codex-agentic-devteam \
  --directory cookiecutter/codex-agentic-devteam

cd <project_slug>

python3 scripts/control_check.py
python3 scripts/generate_dashboard_status.py
python3 scripts/serve_dashboard_preview.py --live
```

## Windows / WSL: Existing Project

```bash
git clone --depth 1 https://github.com/alptekinkekilli/codex-agentic-devteam.git /tmp/codex-agentic-devteam
```

Check conflicts:

```bash
for p in AGENTS.md CLAUDE.md GOVERNOR.md agents scripts docs/controls \
  docs/checklists/pre-push.md public .claude/skills .queue; do
  [ -e "$p" ] && echo "EXISTS $p" || echo "ABSENT $p"
done
```

If there are no conflicts:

```bash
rsync -a \
  --exclude '.git' \
  --exclude 'cookiecutter' \
  --exclude 'public/status' \
  --exclude '.queue/metrics' \
  /tmp/codex-agentic-devteam/ ./

rm -rf /tmp/codex-agentic-devteam

python3 scripts/control_check.py
python3 scripts/generate_dashboard_status.py
python3 scripts/serve_dashboard_preview.py --live
```

## Windows PowerShell: Clone And Conflict Check

Run from the existing project root:

```powershell
git clone --depth 1 https://github.com/alptekinkekilli/codex-agentic-devteam.git $env:TEMP\codex-agentic-devteam
```

Check conflicts:

```powershell
$paths = @(
  "AGENTS.md",
  "CLAUDE.md",
  "GOVERNOR.md",
  "agents",
  "scripts",
  "docs\controls",
  "docs\checklists\pre-push.md",
  "public",
  ".claude\skills",
  ".queue"
)

foreach ($p in $paths) {
  if (Test-Path $p) { "EXISTS $p" } else { "ABSENT $p" }
}
```

If there are no conflicts, copy with PowerShell:

```powershell
robocopy $env:TEMP\codex-agentic-devteam . /E /XD .git cookiecutter public\status .queue\metrics
Remove-Item -Recurse -Force $env:TEMP\codex-agentic-devteam
```

Then switch to WSL or Git Bash for validation and agent runs:

```bash
python3 scripts/control_check.py
python3 scripts/generate_dashboard_status.py
python3 scripts/serve_dashboard_preview.py --live
```

## First Governor Prompt: Existing Project

```text
Your role is Governor.

Read AGENTS.md, GOVERNOR.md, docs/operating-pitfalls.md, and docs/governor-prompts.md.

Manage this existing project with the queue-first Codex devteam workflow. I do not write code; I approve strategic decisions. You coordinate architect, coder, reviewer, tester, and ops through the queue.

Before starting any agent, run pre-flight:
1. Inspect the current project structure.
2. Check .queue/ state.
3. Validate docs/controls/model_routing.json and docs/controls/role_capabilities.json.
4. Run python3 scripts/control_check.py.
5. Run python3 scripts/generate_dashboard_status.py.
6. If useful, start the dashboard with scripts/serve_dashboard_preview.py --live and give me the URL.
7. Verify Codex binary access from PATH or /Applications/Codex.app/Contents/Resources/codex.
8. Report git status if this is a git repo; if not, say so and do not run git init.

Report using:
- step executed
- result
- validation
- next step

Then propose one bounded next step. If the product target is unclear, ask me for objective, acceptance criteria, and allowed_paths. If pending tasks exist, audit model_tier/model_alias/allowed_paths/acceptance_criteria before any claim. Do not start coder until I approve the architect plan.

Dashboard, queue, driver, and config work is governor-direct. Product work goes through architect -> coder -> reviewer -> tester -> ops. No push, PR, or deploy.
```

## First Governor Prompt: New Project

```text
Your role is Governor.

Read AGENTS.md, GOVERNOR.md, docs/operating-pitfalls.md, and docs/governor-prompts.md.

We will build this project from scratch with the queue-first Codex devteam workflow. I approve strategic decisions; you coordinate five role agents: architect, coder, reviewer, tester, and ops.

Before starting any agent, run pre-flight:
1. Inspect the project file structure.
2. Detect the framework/package manager if one exists.
3. Check whether .queue/ is empty.
4. Run python3 scripts/control_check.py.
5. Run python3 scripts/generate_dashboard_status.py.
6. Start the dashboard live and give me the URL.
7. Verify Codex binary access.
8. Identify current app/source/test directories.

Then ask me for a product brief with:
- product objective
- target users
- main screen or workflow
- acceptance criteria
- allowed paths
- forbidden paths
- visual asset needs
- whether HF_TOKEN is needed; check only a boolean and never print the value

When I provide the brief:
1. Create and enqueue only the architect task.
2. Start the watcher.
3. Run only the architect driver.
4. When the architect plan finishes, summarize it for me.
5. Do not start coder until I explicitly approve.

Dashboard, queue, driver, and config work is governor-direct. Product implementation goes through the role loop. Use a watcher for every role. After each role finishes, run control_check and audit the follow-up task. No push, PR, or deploy.
```
