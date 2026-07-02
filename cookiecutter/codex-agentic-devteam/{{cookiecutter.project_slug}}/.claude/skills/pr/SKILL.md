---
name: pr
description: >
  Prove the feature you just built actually works — a fresh verifier sub-agent drives
  the real app — then run the regression sweep, complete the pre-push checklist, and
  close the queue task. Opens a pull request ONLY when the user explicitly asks; the
  default terminal state is "verified + ready to ship", not an open PR. Use when a
  change is ready to ship — "verify this", "prepare to ship", "/pr", or (with an
  explicit request) "open a PR".
user_invocable: true
---

# /pr — prove the feature works, then prepare to ship

You are the **orchestrator + fixer**. Verification splits by who's best at it:

- **The subjective question — "does the feature I just built do what was intended?"** → delegate
  to a fresh **verifier sub-agent** that drives the real app and judges it. Independence (it
  didn't write the code) + context-isolation pay off here. Most changes have no spec — this is
  **agentic verification, not "run the test."** Do it first.
- **Objective, codified checks** (`pytest`, `control_check.py`, JSON validation, lint) → **you**
  run them, after, as a regression sweep. Pass/fail can't be rubber-stamped, and you need the
  error to fix it.

Pairs with `dev-local-setup` (reproducible stack) and `e2e-setup` (the suite).

> **Repo rule (important):** this repo does **NOT** open a pull request unless the user explicitly
> asks for one (`CLAUDE.md`, session policy). The normal terminal state of this skill is a
> verified change on the designated feature branch with the queue task closed and `pre-push.md`
> done — then **stop and report**. Only do Step 6 when the user explicitly says "open a PR".

## 1. Preconditions
On the designated feature branch (never the default branch; never push to a different branch
without explicit permission). Changes committed or stageable. A claimed task in
`.queue/in-progress/` (or note that this is out-of-band).

## 2. Bring up the stack — once
Start it via `scripts/dev-local.sh up` (see `dev-local-setup`). You own it; the verifier reuses it.

## 3. Verify the FEATURE (delegate) → fix → re-verify (loop)
Brief from the task JSON / plan if one exists (point the verifier at its `objective` +
`acceptance_criteria`), else pass requirements inline. Spawn a read-only verifier:

```
You are a read-only verifier. Do NOT edit code. Independently confirm THIS feature works by
driving the running app (the stack is already up). It likely has no automated spec — verify it
agentically.

FEATURE (what a user should now be able to do, and the observable success state):
  <intent / acceptance_criteria>          (or: see task <path>)
HOW TO EXERCISE IT:
  <UI route + steps / API call / CLI>
AUTH (if behind login):
  mint a session first via the repo's session helper and load it before driving.

Drive it (browser via a Playwright driver, or the API/CLI): walk the exact steps,
screenshot/record the success state, judge observed vs expected. Return ONLY:

FEATURE: works | broken
  expected: <criteria>
  observed: <what actually happened>
  evidence: <screenshot/video paths>
```

- **broken** → fix the implementation, then spawn a **fresh** verifier. You never declare the
  feature works yourself.
- Cap at ~3 rounds; if still broken, escalate to the human with the verdict.

## 4. Regression sweep — you run the codified checks; fix red directly
`pytest` · `python3 scripts/control_check.py` · JSON validation for any changed task JSON · lint.
Triage failures (real-bug vs stale-test — see `e2e-setup`); never weaken an assertion to go green.
If a fix here changes feature behavior, re-verify (step 3).

## 5. Close out — the default terminal state
- Move the queue task to `.queue/done/` (or `.queue/failed/` with a clear reason).
- Update the patch registry and session log; append a run note under `docs/runs/`.
- Walk `docs/checklists/pre-push.md` in full (repo-target guard, control_check passes, task
  closed, intended-commit check).
- Commit on the designated feature branch. **Stop here and report** the verdict + evidence.
  Do NOT open a PR. Do NOT push to any other branch.

## 6. Open the PR — ONLY when the user explicitly asked
Lead with the feature proof. Get a **reviewable link** for the success video (GitHub can't play
video inline via automation — upload it somewhere with a stable URL and link it).

```markdown
## What changed
<1–3 lines>

## Feature verified ✅  (verifier drove the app)
- <acceptance criteria> — observed working.  📹 Proof: <url>

## Regression guardrails
- [x] pytest · control_check.py · JSON validation · lint · pre-push.md

## How to reproduce
scripts/dev-local.sh up && <exercise steps>
```

## Rules
- **The feature is the verdict** — a green suite with an unverified feature isn't done.
- **"Does it actually work" → an independent verifier; objective checks → you.**
- **Proof, not claims.** Never claim a feature works without the verifier's observed evidence.
- **No PR unless explicitly requested.** Verified-and-closed-on-branch is the default finish line.

> Isolates *context*, not *environment*: if your stack is single-instance / fixed-port, don't run
> multiple verifiers in parallel.
