---
name: dev-local-setup
description: >
  Scaffold a one-command `dev-local` launcher for this repo (or any codebase).
  Investigates the repo to find its services, ports, and infra dependencies, then
  generates a single `scripts/dev-local.sh` (up/down/status/logs/restart) that runs
  every dev server in one tmux session, plus a short skill doc describing it. Use when
  someone says "set up dev-local", "make a one-command dev launcher", "I want one
  script to start this repo", "scaffold dev-local".
user_invocable: true
---

# Set up a `dev-local` launcher for this codebase

Goal: produce **one script** (`scripts/dev-local.sh`) that a person or agent runs to bring the
whole local stack up — every long-lived dev server in its own tmux window, plus any infra (DB,
cache, queues) the app needs — and a short skill doc so it's discoverable later.

Do NOT start any dev servers yourself. You are *generating* the launcher, not running it. Build
it, syntax-check it, then hand it to the user to run.

## Step 1 — Investigate the repo (don't guess)
Discover the real facts before writing anything:

1. **Package manager & layout** — monorepo markers (`pnpm-workspace.yaml` / `turbo.json` /
   `nx.json`) or single manifests (`package.json`, `pyproject.toml`/`setup.py`, `Cargo.toml`,
   `go.mod`, `Makefile`, `Procfile`, `docker-compose.yml`). Discover the actual app directories
   and start commands from the target repo's package manifests — do not assume any specific paths.
2. **Services to run** — each app/package with a `dev`/`start`/`serve` script, each `Procfile`
   line, or each compose service. Note the exact start command (use the package manager's own
   invocation — e.g. `npm --prefix <app-dir> run dev`, `pnpm -F <workspace> dev`, `python -m
   <pkg>.cli`).
3. **Ports** — grep configs and `.env` for the bind port of each service (`PORT`, `listen(`,
   `next.config`, `vite.config`). Record which talks to which.
4. **Infra dependencies** — Postgres / Redis / Mongo / Kafka? Check `.env`, ORM config,
   `docker-compose`, connection-string defaults. Decide how to provide each locally.
5. **First-run setup** — migrations, seed, codegen, `install`. Note the commands but keep them
   OUT of the default `up` path (offer a separate subcommand).
6. **Env files** — confirm a committed `.env.example`/`.env`; never invent or print secrets. The
   script must not inject credentials (see `CLAUDE.md` Memory Rules).

Write a small table: service → command → port → depends-on. That table is the spec for the script.

## Step 2 — Generate `scripts/dev-local.sh`
Adapt the skeleton in `assets/dev-local.template.sh` (same directory as this skill). Fill in the
discovered services, ports, and infra. Keep these invariants:

- **One tmux session**, one window per long-lived server. Idempotent: re-running `up` leaves
  existing windows alone instead of duplicating them.
- **Preflight** that fails fast with install hints when a required tool is missing.
- **Infra brought up before servers**, reused if already running.
- Subcommands: `up`, `down` (+ `down --all` to stop infra), `status`, `logs <name>`,
  `restart <name>`, `attach`, plus any project-specific one-shots (`migrate`, `seed`).
- Resolve repo root from the script's own location so it works from any cwd.
- No secrets in the script. Print URLs and a port check at the end of `up`.

If the repo has **no infra needs**, drop the Docker/DB parts entirely. Match complexity to the
repo; simpler is better.

Then: `chmod +x scripts/dev-local.sh` and `bash -n scripts/dev-local.sh` to syntax-check. Verify
the read-only `status` path runs cleanly. Do not run `up`.

## Step 3 — Write a short skill doc
Create `.claude/skills/dev-local/SKILL.md` with: frontmatter (`name: dev-local`, a `description`
listing trigger phrases), a service/port table, prerequisites, the subcommand list, and brief
troubleshooting (port-in-use, a window exited, infra not running). One screen — it documents the
script, it doesn't re-explain it.

## Step 4 — Hand off
Tell the user the exact commands: `scripts/dev-local.sh up`, plus any first-run step. List the
URLs. Note any prerequisite they must install or start (e.g. Docker Desktop) before the first `up`.

## Principles
- **Discover, don't assume.** Ports and start commands come from the repo, never convention alone.
- **Idempotent & safe to re-run.** No duplicate servers, no clobbered infra.
- **Right-sized.** A 3-service monorepo with Postgres+Redis needs the full skeleton; a single
  Next.js app needs ~30 lines. Don't over-build.
- **Never run servers or print secrets.** Generate, syntax-check, hand off.
