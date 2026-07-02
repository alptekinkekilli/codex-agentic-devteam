---
name: new-loop
description: Spin up a new loop (recurring workstream) in this dev-team repo — gather its charter, scaffold docs/loops/<loop>/README.md, then do ONE real test run that drives the loop once through the .queue/ lifecycle and record it in the loop README's Timeline and in docs/runs/. Use when the user says "set up a new loop", "create a workstream/beat", "start a recurring job", or names a cadence-driven job the team should own.
---

# new-loop — spin up a recurring workstream

A **loop** is a recurring thread of work this team owns: a charter, a cadence, and the
artifacts/queue tasks it produces. This skill creates one, proves it works with a single real
run through the `.queue/` lifecycle, and leaves behind a `docs/loops/<loop>/README.md` that is
the loop's live state.

This adapts the AI Builder Club "loop engineer" model to *this* repo: instead of free-floating
`domains/`, a loop's recurring work is dispatched as bounded task JSON through `.queue/` and
owned by the existing roles (architect → coder → reviewer → tester → ops).

## When to use
The user wants to stand up a recurring workstream/beat/job (e.g. "a weekly dependency-audit loop",
"a queue-hygiene loop", "a memory-redaction audit loop"). Do **not** use this for a one-off task
— that's a single task JSON enqueued normally, or a `docs/` note.

## Inputs to gather (ask only what's missing)
Pull these from the user's request; ask a short clarifying round only for what you can't infer:

1. **name** — kebab-case, the loop's home folder (`docs/loops/<name>/`). Keep it short.
2. **goal** — one line: the outcome this loop drives.
3. **cadence** — `manual` / `daily` / `weekly` / a cron expr. Default `manual`.
4. **what it does** — what the loop consumes (a queue? signals? data? an inbox? a URL?) and
   produces (a `docs/` note? new task JSON for the `coder`/`reviewer` roles? a report?).
5. **tools/data** — any sources or credentials it needs. Note them; point at a setup skill or
   `.env` rather than inlining secrets (see Memory Rules in `CLAUDE.md`).

If the request is already specific, infer all five and just confirm in your summary — don't
interrogate.

## Procedure

Work **one bounded step at a time** and validate each step (per `CLAUDE.md` Rules).

### 1. Ensure the substrate exists
From the repo root, make sure these exist (create only what's missing — don't recreate what's
already there):
- `docs/loops/README.md` — the loop schema/charter index (create with a short header if absent).
- `.queue/{pending,in-progress,done,failed,events}/` — already present; do not recreate.

Do **not** pre-create new `docs/` kinds or queue phases the loop hasn't earned yet.

### 2. Scaffold the loop README
Create `docs/loops/<name>/README.md` filled with the gathered inputs. Required sections:
- Frontmatter: `kind: loop`, `name`, `status: active`, `goal`, `cadence`, `owner_role`.
- A 2–4 line description.
- `## Current focus`
- `## Backlog` — the loop's to-dos inline (these stay here until they're enqueued as task JSON).
- `## Timeline` — empty, append-only.
- `## Metrics` / `## Evidence` placeholders if relevant.

Collision check: if `docs/loops/<name>/` already exists, stop and ask whether to update it
instead of overwriting.

### 3. Do ONE real test run
This is the point of the skill: prove the loop actually runs, not just that the folder exists.

**Actually run the loop once, at small scale** — do whatever the loop is meant to do (triage a
few real queue items, pull one real SERP, fetch the inbox, scope one code change, run one
analysis). Use the loop's real tools/data where you can; if a credential is missing, do the
furthest-reachable dry run and note the gap.

If the loop ships work, the run's natural output is **one bounded task JSON enqueued via the
lifecycle**, not a direct edit:
- Write a task JSON (fields: `id`, `title`, `role`, `status: pending`, `created_at`, `objective`,
  `allowed_paths`, `acceptance_criteria`) under `docs/tasks/` or a scratch path.
- Enqueue it: `python3 scripts/enqueue.py <task-file>`.
- Validate any changed task JSON and run `python3 scripts/control_check.py`.

**Producing an artifact/task is optional.** A legitimate run may surface nothing worth filing —
that's a real result, not a failure. Only enqueue a task or file a `docs/` note if the run
genuinely produced one.

Whatever happens, the run has two **required** outputs:
- Append one dated line to the loop README's `## Timeline`:
  `YYYY-MM-DD | test run — <what you did and what you found / "nothing actionable yet">`.
- Append a short run record under `docs/runs/` (the global feed):
  the loop name, what the first run did/found, and refs to `docs/loops/<name>/README.md` plus any
  task enqueued or note created.

### 4. Validate, then report back
- Run `python3 scripts/control_check.py` (docs + queue changed).
- Walk `docs/checklists/pre-push.md` before any commit/push.
- Summarize to the user: the loop's charter (the five inputs), what the test run did and found,
  any task/artifact created (or "none — nothing actionable this run"), missing tools/credentials
  to wire up, and how to run it again (the cadence + entry point). Keep it tight.

## Notes
- **Don't gold-plate the scaffold.** A loop README is live state, not a spec — start lean and let
  it accrete via its Timeline.
- **One loop = one separable workstream.** If what the user described is really part of an
  existing loop or phase, say so and add it there (a backlog line) instead of a near-duplicate.
- **Respect the boundaries:** loops never deploy, store secrets, or push to the core repo. They
  produce bounded task JSON; the role agents execute under their own contracts.
- For loops that ship code, point the README's Backlog at the `pr` skill for the verify-before-
  ship gate.
