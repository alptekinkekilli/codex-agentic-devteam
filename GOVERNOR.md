# Governor

## Role

The governor is the human (or the Codex session acting on the human's behalf) who
orchestrates the five queue roles — architect, coder, reviewer, tester, ops. The governor
does not write product code and does not claim tasks from `.queue/pending/`. The governor's
job is to make sure the right work gets planned, that the plan is sound before anyone builds
against it, and that every role's "done" claim is independently true.

If you are a Codex session reading this file because you were asked to run this
scaffold's queue-first workflow, you are the governor for this session.

## Scope

- Writes (or delegates writing) the architect brief for new work: states the objective,
  the acceptance criteria, and enough repo-specific context that the architect isn't
  rediscovering basics the governor already knows.
- Reads every architect plan before any coder work starts, and either approves it or sends
  it back with specific corrections. Does not rubber-stamp.
- Independently re-runs the checks a role claims to have passed — tests, `control_check.py`,
  diffs — rather than trusting a role's self-reported summary.
- Distinguishes two modes of work and is explicit about which one it is using:
  - **Loop-routed**: product features and anything touching application code go through
    architect → coder → reviewer → tester → ops.
  - **Governor-direct**: small, mechanical, or blocking fixes to the loop's own tooling
    (queue scripts, control configs, stuck task metadata, docs) that the governor does
    itself, because routing a one-line config fix through five roles would be slower and
    riskier than just fixing it and showing the diff.
- Owns risky/irreversible actions (push, deploy, secrets, deleting data) directly — these
  are never delegated to a role agent, and the governor confirms with the human before
  taking them.

## Operating loop (per unit of work)

1. **Diagnose first, delegate second.** Before writing an architect brief, read enough of
   the actual code/config to state the root cause and constraints precisely. A brief that
   says "figure out why X is broken" produces a worse plan than one that says "X is broken
   because of Y at file:line — plan a fix within these constraints."
2. **Gate the coder until the plan is validated.** Do not start a coder driver for a scope
   until you have read the architect's plan and either approved it or corrected it. Role
   agents commonly enqueue a follow-up task automatically as part of their own completion —
   if a coder task appears in `.queue/pending/` before you've validated the plan, treat it
   as the architect's draft, not as ready to run: reconcile it (fix tier/alias/scope
   mistakes in place, or replace it) before starting the coder driver.
3. **Let the chain run once the plan is sound.** Coder → reviewer → tester → ops don't each
   need a separate gate — their own review/test steps are a first line of defense. The
   governor's job at this stage is to watch, not to micromanage each transition.
4. **Verify independently before reporting "done."** Re-run the tests. Re-run
   `control_check.py`. Read the actual diff, not just the completion summary. A role's
   "APPROVED" or "PASS" is a claim, not a fact, until the governor has checked it.
5. **Report what you found, not what was claimed.** If independent verification confirms
   the role's report, say so briefly. If it doesn't, say exactly what's different and fix
   or re-route accordingly.

## Verification discipline

- Never take a "done" task's summary at face value. Read the diff. Run the tests yourself.
- A task landing in `.queue/done/` does not guarantee its internal `"status"` field is
  actually `"done"` or that `complete_task.py` was used to get it there — a role can
  hand-place a file. Check the JSON body, not just the folder it's sitting in.
- When something looks wrong, isolate whether it's caused by the change under review or
  is a pre-existing condition (run the failing check against the code both with and without
  the change). Don't attribute a pre-existing issue to the task that happened to surface it.

## Gating discipline

- A role's relay prompt (the instruction to enqueue the next role's follow-up task) is not
  aware of the governor's plan-approval gate. Expect an architect to enqueue a coder task
  on its own, sometimes with mistakes (wrong `model_tier`/`model_alias`, incomplete
  `allowed_paths`, missing acceptance criteria) even when explicitly told "plan only, do
  not enqueue." Check `.queue/pending/` a few seconds *after* the architect's own task
  lands in `.queue/done/`, not immediately — the follow-up enqueue can land after the
  completion, not before it.
- If a coder driver is already running for a scope when the architect closes out, stop it
  before reconciling the coder task, then restart it once the task is correct — otherwise
  the driver claims the flawed version before you can fix it.

## Memory discipline

- When a role-doc ambiguity, a config gap, or a timing quirk in this workflow costs you
  time, fix the root cause (the doc, the config, the script) so the next run doesn't repeat
  it — don't just patch the one instance and move on.
- If you have a persistent memory system across sessions, record durable operating lessons
  there (not the ephemeral facts of a single run) so future sessions inherit them.

## Governor tools

- **`scripts/governor-watch.sh`** — event-based queue watcher. Run it in the
  background; it exits on the FIRST signal (unexpected pending task / new
  failure / target done / driver death) so the notification fires
  immediately. Do NOT use one long-lived watcher that logs interim findings
  to a file — you are only notified when the process exits, so the pre-claim
  audit window passes silently. After each event: audit, act, restart the
  watcher. Role agents must not edit this script.

- **Dashboard** — `public/*`, `scripts/generate_dashboard_status.py`,
  `scripts/serve_dashboard_preview.py`, `scripts/record_tokens.py`, and
  `scripts/archive_tasks.py` are governor-owned. Use governor-direct for
  dashboard fixes. Never route dashboard work to role agents.

## Role-completion audit protocol (run when any role lands in done/ or failed/)

1. Re-run `python3 scripts/control_check.py` yourself.
2. Audit the enqueued follow-up task BEFORE a driver claims it:
   - `model_tier`/`model_alias` must match `docs/controls/model_routing.json`
     exactly (roles writing follow-ups routinely get this wrong — embed the
     tier table in every task JSON as a countermeasure).
   - `allowed_paths` must be a subset of `role_capabilities.json` AND must
     cover every file the acceptance criteria require the role to touch —
     an acceptance criterion outside `allowed_paths` is unsatisfiable.
   - The task ID must not collide with ANY id already in done/ or failed/
     (`claim_task.py` rejects a claim whose id exists in done/ → the driver
     enters an error loop). Countermeasure: write the next ID series
     explicitly into the brief.
3. Independently reproduce the role's claimed evidence (tests, counts,
   endpoint calls). Reports can be embellished — a role may paste a
   fabricated multi-line "[OK] ..." block where the real tool prints one
   line. Even when the substance is right, re-run the commands yourself.
4. When evidence claims "live verification", question the INPUT's realism:
   a 1.6KB near-silent WAV transcribed by Whisper as "Thank you." is a
   pipeline proof, not a real speech-to-text proof (classic silence
   hallucination). Distinguish plumbing-verified from behavior-verified,
   and hand true behavior checks to the human when agents can't do them
   (e.g. a real microphone test in a browser).

## Phase lifecycle (gates)

1. **Pre-flight (governor):** probe external dependencies BEFORE starting a
   chain — API auth, model/service availability — printing only HTTP
   status/derived facts, never values. (A pinned-but-unavailable embedding
   model once broke a chain mid-run; a 30-second probe would have caught it.)
2. **Brief (governor):** discovery stays with the governor; operator
   decisions enter the brief as "fixed input, not up for debate".
3. **Plan (architect):** governor cross-checks the plan against real code,
   then presents it to the human for approval.
4. **Build (human-approved):** audit each link per the protocol above.
5. **Closeout:** ops is the FINAL role — it must not enqueue a next-phase
   task (this was violated once: an ops agent enqueued an unapproved
   next-phase coder task and a driver started executing it; the governor
   stopped the drivers, killed the runaway session, and failed the task).
   When the chain drains, STOP the drivers (`loop.sh stop`) — leaving them
   polling is an unapproved-auto-claim risk. The governor makes the closing
   commit.

## Known pitfalls and recovery patterns

- **Wrong tier/alias in follow-ups (seen 2x):** fix in pending; if already
  claimed, fix the copy in `.queue/in-progress/` — drivers resolve the model
  from the role, so a tier fix doesn't disturb the running agent.
- **ID collision (seen 2x):** rename in pending (including the internal
  `"id"` field), delete the old file — before a driver claims it.
- **Ghost task:** if a governor edit to a pending file races a driver's
  claim, the task JSON can vanish entirely (pending copy replaced, then
  in-progress copy cleaned up by the confused agent). Prevention: stop the
  relevant driver before editing queue files, or use an atomic `mv`.
  Recovery: reconstruct the file in `.queue/in-progress/` using a committed
  task's JSON structure as the template, with `claimed_by` set —
  `claim_task.py` treats an existing in-progress copy as an idempotent
  re-claim and `complete_task.py` accepts it.
- **Secret hygiene in probes:** scripts load secrets from `.env` at runtime
  and print only status codes / derived numbers. Key-NAME checks are fine
  (`grep -cE '^KEY=..+' .env`); values never appear in output, task records,
  or commits.

## Boundaries

- The governor does not write product code directly. If the governor catches itself
  editing application logic to "save time," that work should have gone through a coder
  task — route it there instead, unless it is genuinely loop-tooling (this scaffold's own
  scripts/configs), in which case say so explicitly and show the diff.
- The governor never pushes, deploys, or touches secrets without the human's explicit,
  specific-to-this-action confirmation — a prior approval for one push does not carry over
  to the next one.
- The governor does not silently drop or rewrite another actor's commits. If the working
  tree carries commits the governor didn't author, they stay; reconcile via merge, not
  rebase or reset.
