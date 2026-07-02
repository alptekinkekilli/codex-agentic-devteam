# Governor Prompt Library

Use these prompts from a supervising Codex/Governor session. Replace
`<scope>` and task ids.

## Continue After Coder Done

```text
Coder result accepted. Continue with reviewer in isolation.

Before starting:
- Confirm no reviewer/tester/ops driver is already running for <scope>.
- Audit pending reviewer task model_tier/model_alias against docs/controls/model_routing.json.
- Audit allowed_paths against docs/controls/role_capabilities.json.
- Include all later coder follow-ups in reviewer context if they happened after the reviewer task was first created.

Watcher:
scripts/governor-watch.sh <scope> --done <reviewer-task-id>

Driver:
bash scripts/role-agent.sh reviewer <scope>

When watcher exits:
1. Run python3 scripts/control_check.py.
2. Audit reviewer done/failed body.
3. Summarize findings by severity and file reference.
4. Audit pending tester follow-up if one exists.
5. Do not start tester until I approve.
```

## Continue After Reviewer Approved

```text
Reviewer result accepted. Continue with tester in isolation.

Watcher:
scripts/governor-watch.sh <scope> --done <tester-task-id>

Driver:
bash scripts/role-agent.sh tester <scope>

When watcher exits:
1. Run python3 scripts/control_check.py.
2. Audit tester done/failed body.
3. Re-run the exact validation commands the tester claims passed.
4. If failures are pre-existing, distinguish them from this change.
5. Audit pending ops follow-up if one exists.
6. Do not start ops until I approve.
```

## Continue After Tester Passed

```text
Tester result accepted. Continue with ops in isolation.

Watcher:
scripts/governor-watch.sh <scope> --done <ops-task-id>

Driver:
bash scripts/role-agent.sh ops <scope>

When watcher exits:
1. Run python3 scripts/control_check.py.
2. Audit ops done/failed body.
3. Confirm ops did not enqueue a next-phase task.
4. Stop any remaining drivers for <scope>.
5. Summarize changed files, validation, residual risks, and whether a commit is ready.
```

## Driver Or Tooling Failure

```text
This is a driver/tooling failure, so use governor-direct. Do not start or
restart any role driver until the tool is fixed.

Diagnose:
- command -v codex || true
- /Applications/Codex.app/Contents/Resources/codex --version || true
- tail -n 200 /tmp/agent-loop-<scope>/<role>.log
- python3 scripts/control_check.py

Fix only queue/dashboard/driver/config tooling. Then run:
- bash -n scripts/role-agent.sh scripts/loop.sh scripts/governor-watch.sh
- python3 -m py_compile scripts/*.py
- python3 scripts/control_check.py
- python3 scripts/generate_dashboard_status.py

After a driver fix, restart only the next pending role in isolation. Do not run
the whole build chain until the fixed driver has proven claim + close behavior.
```

## Hugging Face Asset Follow-Up

```text
Create or run a bounded HF asset follow-up only if the product requires a raster
asset and the previous implementation used a fallback.

Before running:
python3 -c 'import os; print("HF_TOKEN in env:", bool(os.getenv("HF_TOKEN")))'

Never print the value.

Acceptance criteria:
- Use generate_image.py or the documented HF image workflow.
- Read HF_TOKEN only from environment/project .env.
- Write output under the task's allowed asset path.
- Record prompt, model, and output path in docs/.
- Do not write token values into task JSON, logs, dashboard, docs, or chat.
```
