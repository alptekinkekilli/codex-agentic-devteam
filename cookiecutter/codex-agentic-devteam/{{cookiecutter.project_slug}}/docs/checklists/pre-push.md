# Pre-Push Safety Checklist

Use this before every commit and push.

## Workspace Target

- [ ] Say the intended repo out loud in the session log or final note.
- [ ] `pwd` or tool workdir matches the intended repo.
- [ ] `git rev-parse --show-toplevel` matches the intended repo root.
- [ ] If the repo has not been initialized with git yet, stop before any push-related action.

## Wrong-Repo Edit Guard

- [ ] `git status --short --branch` in the intended repo shows only expected files.
- [ ] `git diff --name-only` in the intended repo matches the task's allowed paths.
- [ ] No accidental edits exist outside the task's allowed paths.

## Remote Guard

- [ ] `git remote -v` shows the expected push target.
- [ ] Push target is the intended remote for this repository.
- [ ] The push command names the remote and branch explicitly.

## Final Gate

- [ ] `python3 scripts/control_check.py` passes.
- [ ] Current task is in `.queue/done/` or `.queue/failed/`.
- [ ] Patch registry and session log are updated.
- [ ] `git log -1 --oneline --decorate` shows the intended checkpoint before pushing.
