---
name: setup-codebase-harness
description: >
  Master skill — set up the full agent harness for a repo so the team can work it
  reliably: legible (slim map + docs/ system-of-record + control_check.py invariants),
  executable (one-command dev stack), verifiable (e2e gate + verify-before-ship loop),
  plus commit hygiene (pre-push.md) and entropy control. Use when onboarding a new/
  unfamiliar repo to agent-driven development — "set up the harness", "make this repo
  agent-ready", "harness this codebase".
user_invocable: true
---

# Set up the codebase harness

**Harness engineering:** the model is fixed — what you engineer is the *scaffolding* around it
(the environment, the docs, the feedback loops) so an agent can build and verify software with
minimal human attention. Humans steer; agents execute. Your job is to make the repo **legible,
executable, and verifiable.**

Work **incrementally and depth-first** (one bounded step at a time, validate each — `CLAUDE.md`):
assess what exists, build the one missing capability, use it to unlock the next. Don't boil the
ocean. When an agent struggles, the fix is almost never "try harder" — ask *"what capability is
missing, and how do I make it legible and enforceable?"* and add it.

This skill orchestrates the focused sub-skills: **`dev-local-setup`**, **`e2e-setup`**, **`pr`**.

## 0. Assess
Survey the repo: stack, package manager, services/ports, infra deps, existing docs/tests/CI, and
the *implicit* rules (buried in READMEs, task JSON, people's heads). In a new repo: discover the
package manager, app directories, test directories, and existing scripts. Note what's missing per
pillar below.

## 1. Legible — the agent can reason about the repo
> What the agent can't see doesn't exist. Knowledge in chat threads / heads is invisible — push
> it into versioned, repo-local artifacts.

- **a) Map, not manual.** Keep the root agent doc (`CLAUDE.md`) a short **table of contents**:
  one-line overview, roles, golden **Rules**, Memory/Validation defaults, and where to look. Depth
  lives in the **`docs/` system-of-record** (architecture, checklists, controls, reviews, runs,
  tasks…). A monolithic instruction file rots — keep the map small and stable.
- **b) Mechanical controls with remediation.** Promote prose golden rules into **checks** —
  `scripts/control_check.py` is this repo's control gate; add one assertion per invariant (queue
  schema, allowed_paths discipline, no-secrets in memory, repo-target guard). **Write each failure
  message to inject the fix** ("X isn't allowed here — do Y") so remediation lands in agent
  context. Run it after every docs/queue/control change.
- **c) (later) Keep docs honest.** A freshness pass (a `new-loop`) that flags `docs/` notes no
  longer matching the code and enqueues fix-up tasks.

## 2. Executable — the agent can run & drive the app
- **`dev-local-setup`** → a one-command, reproducible local stack (`scripts/dev-local.sh up`)
  running every dev server (e.g. your-app-dir) + any infra.
- Make the app **drivable**: browser via a Playwright driver; logs reachable.
- *Advanced:* boot per git worktree so parallel role-agents don't collide.

## 3. Verifiable — the agent can prove it works
- **`e2e-setup`** → a trustworthy e2e gate: real flows (not bypass), a reusable auth/session
  helper, layered client → server → product assertions, evidence, sandbox-only external services.
- **`pr`** → the verify-before-ship loop: a fresh **verifier sub-agent drives the real app** to
  confirm the just-built feature works; the main agent fixes until green, runs the regression
  sweep (`pytest` · `control_check.py` · JSON validation), completes `docs/checklists/pre-push.md`,
  and moves the task to `.queue/done/`. (PR only on explicit request — see that skill.)

## 4. Others — keep it coherent over time
- **Commit hygiene**: `docs/checklists/pre-push.md` is the gate (repo-target guard, control_check,
  task closed, patch registry + session log updated). Keep merge gates light — corrections are
  cheap, waiting is expensive.
- **Garbage collection**: encode golden principles in `control_check.py`, then run periodic
  cleanup loops that enqueue small refactor tasks — pay tech debt down continuously.
- **Agent-to-agent review** for correctness-critical changes — use the independent `reviewer` and
  `tester` roles, never self-review (per `agents/*.md`).

## Order & what you leave behind
**1a (map) → 2 (dev-local) → 3 (e2e + pr)**, then **1b (controls)** and **4** as the repo matures.
The artifacts — slim `CLAUDE.md` + `docs/`, `scripts/dev-local.sh`, an `e2e/` suite, the `pr`
skill, and `control_check.py` invariants — are each a reusable, legible capability that compounds.
Prefer "boring", composable, stable tech the agent can fully model.
