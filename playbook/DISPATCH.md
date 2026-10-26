# Dispatch playbook

Read only the section you need.

## 1. Dispatch and hand-back (same for Claude and Codex)

1. Check the real IDs and status of running workers. Confirm the three
   parallelism conditions (no unlocked heavy job, no overlapping write scope,
   ~10-line hand-back). If the health check says the oldest worker is too old
   or the user is waiting, collect hand-backs before dispatching more.
2. Write `tasks/<task-id>.md` from `contracts/templates/task-brief.md`. For
   high-leverage tasks, write a Task Spec instead and render it with
   `contracts/build_task_packet.py` (see `PROMPT_CONTRACT.md`).
3. Record the actual start time and the worker ID in `NOTES.md`. A successful
   launch is not progress.
4. Do other independent work. Background jobs report completion as an event;
   keep exactly one watcher per task. On timeout, check the exit status and the
   log once. Never start a duplicate of the same task.
5. On hand-back, set the status to "handed back, awaiting check". Re-run the
   acceptance commands and look at the frames or screens the brief names. Confirm
   only allowed files changed and the base did not drift. If the main branch moved,
   resolve the difference; never overwrite whole files.
6. Integrate only what passes. Return failures with the actual output; at most two
   rounds of fixes per failure. Integrate what came back before dispatching more.
7. Keep a one-line task log entry: start and hand-back time in UTC, result,
   rework reason, location of the output. Record times; do not estimate them.

### Codex in a worktree

Preconditions: `git rev-parse --verify HEAD` succeeds, the source the worker
needs is committed, keys and generated output are excluded.

```sh
tools/dispatch_codex.sh <task-id> [model]   # run in the background, wait for exit
```

The script creates `../<repo>-wt/<task-id>` on branch `task/<task-id>` at the
current HEAD, checks the worktree is really at that SHA, and runs
`codex exec -s workspace-write` with the brief on stdin. After it exits:

- `git -C <worktree> diff --stat`: only allowed files changed?
- re-run the acceptance commands;
- commit in the worktree, cherry-pick to main, `git worktree remove` (no `--force`).

Pin the model explicitly. In our first session the CLI's default model was
rejected by the account, which nobody noticed for hours: Codex got zero tasks.
Verify the model once with a read-only smoke task before relying on it, and
re-check before any announced retirement date.

Independent review of uncommitted changes: `codex exec review --uncommitted`.
Check `--help` on the installed CLI before scripting against it.

### Heavy local jobs

```sh
python3 tools/run_locked.py --lane render -- <command and args>
```

Run it in the background and wait for the completion event. The wrapper finds the
same lock from any worktree of the repo, writes output to `tasks/run-logs/`, and
returns the exit code, the log path and the last 20 lines (60 plus earlier error
lines on failure). `RUN_LOCKED_VERBOSE=1` streams instead. Verify one question per
job: low-resolution key frames before full clips. The lock only covers jobs
started through the wrapper; anything already running must be finished by
whoever started it.

## 2. Wrap-up, hand-over and compaction

1. Stop new dispatches and polishing. List every real worker and background job ID.
   Tell running workers to save their best version and hand back.
2. Keep patches, actual acceptance output, previews, and the list of unfinished and
   unverified items. Record failures and cancellations as such. Do not kill a
   worker that is still writing.
3. Collect results; compare worktrees with main; note what is merged and what is not.
4. Overwrite the "Now" section of `NOTES.md` with the latest state. Move history to
   `docs/` or the hand-back files and keep only an index.
5. Then ask the user to run `/compact`. After compaction, the first action is to
   read `NOTES.md`, the second is to read the hand-over file if one exists, and the
   third is to tell the user the recovered goal, queue and next step.

## 3. Health check

- `python3 tools/health.py` reads the session transcript and appends a line to
  `tasks/health/metrics.jsonl`. Install the hook from
  `tools/hooks/claude-settings.example.json` into `.claude/settings.json`.
- Thresholds (starting values; change them only with a decision record):

  | Metric | Yellow | Red | Red action |
  |---|---|---|---|
  | Context | 120k | 180k | Save `NOTES.md`, confirm the write, ask for `/compact`, stop dispatching |
  | Unanswered user message | 90 s | 180 s or 3 messages | Stop tools, answer everything |
  | P1 in progress | | 3 | Ask the user to pick |
  | Oldest worker | 20 min | 40 min | Check once, then collect or split |
  | Heavy jobs at once | | 2 | Find who bypassed the lock |

- Independent report: when the last one is older than 30 minutes and there was
  activity, the hook starts a fresh read-only Codex session with
  `tools/health-review-prompt.md` and the recent numbers. The result is injected
  on the next user message. A report that does not appear within 10 minutes turns
  red. Manual: `python3 tools/health.py --report`. Model: `HEALTH_CODEX_MODEL`.
- Limit: it only fires when the user sends a message. During a long model turn,
  the warning arrives late too. The user's interrupt key is the only real preemption.

## 4. Two-track review (cheap draft first)

For any output where structure is expensive to change late (video, level layout,
UI flow):

1. **Overview of the cheap draft.** Sample the whole thing at fixed intervals plus
   every transition, with a burned-in timecode. Placeholders are fine.
2. **Collect feedback.** The user points at timecodes. Merge each batch into one
   sentence and put it in the queue; do not start on every remark.
3. **Batch changes** at a natural pause. Re-render only affected frames.
4. **Lock** only when the user explicitly says so. Write the lock as the spec for
   the expensive version: duration, camera path, mood, required objects, what is
   forbidden.
5. **Expensive version** only for locked sections, 3–5 key frames before a full
   section. A structural change goes back to the draft track; small fixes under
   5 minutes may be done in place.
6. One queue, one set of workers, one heavy-job lane for both tracks. The same
   section is never on both tracks at once.
