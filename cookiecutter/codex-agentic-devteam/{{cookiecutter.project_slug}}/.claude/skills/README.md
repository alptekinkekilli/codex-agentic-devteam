# Skills

User-invocable Claude Code skills for this dev-team repo. Each skill is a
`<name>/SKILL.md` with YAML frontmatter (`name`, `description`) and a procedure.

## Provenance

Ported from the AI Builder Club **loop-engineer-template**
(`github.com/AI-Builder-Club/loop-engineer-template`, by Jason Zhou) and **adapted to this
repo's conventions** — the `.queue/` lifecycle and role agents, the `docs/` system-of-record,
`scripts/control_check.py`, and `docs/checklists/pre-push.md`. They are not verbatim copies.

## Skills

| Skill | What it does |
| --- | --- |
| `new-loop` | Spin up a recurring workstream: charter in `docs/loops/<name>/`, one real test run through `.queue/`, logged in the Timeline + `docs/runs/`. |
| `setup-codebase-harness` | Master skill — make a repo legible / executable / verifiable. Orchestrates the three below. |
| `dev-local-setup` | Generate a one-command `scripts/dev-local.sh` launcher (asset skeleton in `dev-local-setup/assets/`). |
| `e2e-setup` | Stand up a trustworthy end-to-end test gate (real flows, layered assertions, evidence). |
| `pr` | Prove the feature works (independent verifier) + regression sweep + `pre-push.md` + close the queue task. **Opens a PR only on explicit request.** |

## Key adaptations from the upstream template

- The template's free-floating `domains/` + `signals/` + `docs/` model is rewired onto this repo's
  `.queue/` lifecycle: a loop's recurring work is dispatched as bounded **task JSON** owned by the
  existing roles (architect → coder → reviewer → tester → ops).
- The `pr` skill respects this repo's rule: **do not open a pull request unless explicitly asked**.
  Its default finish line is "verified + queue task closed + pre-push done" on the feature branch.
- Validation hooks use this repo's gates: `python3 scripts/control_check.py`, JSON validation for
  changed task files, and `docs/checklists/pre-push.md`.
