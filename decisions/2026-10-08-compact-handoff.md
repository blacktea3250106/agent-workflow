# 2026-10-08: compaction hand-over protocol

Drafted by a Codex worker (write scope: this one file), then reviewed by the
orchestrator. Status at the time of writing: proposal, waiting for the user's
confirmation before the rules file changes.

## Problem

- `/compact` is a CLI command only the user can type. The orchestrator cannot run
  it, and must never `/clear`.
- In the session it showed up: context sat at 188k–193k (red) while the
  orchestrator kept working, and the user asked several times "can't you compact
  yourself?"
- The health warning told the orchestrator to "save NOTES.md and compact" but did
  not include the step that actually matters: ask the user.

## Protocol

**Yellow (120k–180k)**: before the next reply, update `NOTES.md` with goal, queue,
in-progress P1, running workers and jobs, finished-but-unmerged results, pending
user decisions. End the reply with a fixed line:
`[COMPACT SUGGESTED] Context is yellow; NOTES.md is updated. Please run /compact when convenient.`
Existing P1 work may continue; a new dispatch needs a stated reason.

**Red (180k+)**: stop dispatching. Allowed: replying, updating `NOTES.md`,
integrating results that came back, recording running jobs. End the reply with:
`[COMPACT REQUIRED] Context is red; NOTES.md is updated and dispatching has stopped. Please run /compact now.`
New user requests go into the queue only.

**After compaction**: first action reads `NOTES.md`, second reads the hand-over
file if any, third tells the user the recovered goal, queue and next step.

## How it is checked

- `NOTES.md` modified after the warning time.
- The fixed line appears in the reply.
- No new dispatch, job or worker between a red warning and the compaction.
- The first reads after compaction include `NOTES.md`.

The independent health report checks the same three questions.

## Not doing

- No automated `/compact` hack, no simulated user input.
- No new always-on agent or service; this extends the existing health check.

## Data point

The first manual compaction after the fixes took 77 s and went from 553,549 to
10,321 tokens. That is context size, not a claim about reply speed.
