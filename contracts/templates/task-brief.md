# Task brief: <task-id>

Saved as `tasks/<task-id>.md` and passed to the worker unchanged. If a line below
cannot be filled in, the task is not ready to dispatch.

## Input
- Base commit: `<sha>`. Check `git rev-parse HEAD` before anything else and report it if it differs.
- Relevant files / sections: `<paths>` (read only these, not the whole repo)
- Latest user decisions that apply: `<quote them, with time>`
- Shared read-only assets: `<absolute paths>`. Git-ignored files do NOT exist in your worktree;
  if you need one of them and it is not listed here, stop and say so.

## Output
- What to hand back: `<files / behaviour>`
- Stop point for this round: `<one verifiable thing>`

## Files you may change
- `<exact paths>`. Everything else is read-only. Your working root is the worktree, not the main checkout.

## Do not
- Add features, dependencies or refactors not listed above.
- Dispatch other agents. Edit the orchestrator's status file.
- Start heavy jobs except through `tools/run_locked.py`.
- Read or print `.env*` or any key.

## Acceptance
- Commands: `<command>` -> expected: `<result>`
- What a human must look at: `<frame / screen / page>`

## Hand back (about 10 lines; long output goes to a file)
- Changed files or patch path, base SHA, actual acceptance output,
  where to preview, what is unfinished or uncertain, start and finish time in UTC.
