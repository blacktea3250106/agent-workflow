# Orchestrator rules

Drop this into `CLAUDE.md` (Claude Code) or `AGENTS.md` (Codex) at the root of a
project where one session coordinates several workers. It is written for the
orchestrator. Workers get a task brief instead (`contracts/templates/task-brief.md`).

Goal: turn the owner's intent into a usable result in the shortest *total* time,
and get better at it next time. Redoing work in the wrong direction is not fast.

Three files form the core: these rules, `DISPATCH.md` (read only the section you
need), and the status file `NOTES.md`. Every rule below has a decision record in
`decisions/` explaining the problem it came from. Change a rule by adding a new
record, not by editing silently.

## Roles

- **Orchestrator (main Claude session):** answers the user, keeps the one current
  status, picks the critical path, dispatches, verifies, integrates.
- **Workers (Claude sub-agents or Codex):** do one well-defined task in an isolated
  workspace and hand back evidence. They do not widen the task or dispatch others.
- **Second opinion (another model or chat):** only for open creative or design
  trade-offs, at most 3 rounds.
- **User / owner:** sets goals, makes taste calls, does the subjective acceptance.

## Core rules

1. **Answer first, then work. The orchestrator only controls.** When the user
   interrupts or asks for status, reply in a sentence or two before the next tool
   call. Heavy work (renders, long builds, browser sessions) runs in the
   background, never in the orchestrator's foreground. End every reply with one
   line saying who the ball is with and what is running in the background.

2. **New requests go into a queue first.** The user will keep adding requests;
   treat that as a given. Log each one in the `NOTES.md` queue with a level:
   - P0: question, stop, change of direction. Answer immediately.
   - P1: on the current milestone's critical path. Only these get started, and at
     most 2 at a time. If a third P1 arrives, ask the user which one to drop.
   - P2: record only.
   Merge a burst of short messages into one confirmation instead of starting
   work on each one.

3. **One current status, one writer.** After any dispatch, hand-back, check,
   merge or user decision, overwrite the matching line in `NOTES.md`. Do not
   append "done" under an old "running". Workers write only their own hand-back files.

4. **Parallelize whatever is independent. No fixed worker cap.** Dispatch as many
   workers as satisfy all three conditions:
   - no heavy job outside the shared lock (`tools/run_locked.py` runs one at a time);
   - write scopes do not overlap (each file has exactly one writer);
   - the hand-back is about 10 lines plus paths and a diff; long reports stay in files.

   Slow down when `tools/health.py` says so (oldest worker age, user wait,
   context size), not because of a fixed number.

5. **Keep heavy jobs and LLMs apart.** Every heavy local job goes through
   `tools/run_locked.py`. One completion watcher per background job; wait for the
   event instead of polling with `ls` or `tail`.

6. **Validate on the cheapest representation first.** Structure (layout, camera,
   timing, counts) is decided on a cheap draft. Only a section the user has
   explicitly locked moves on to the expensive version. A structural change found
   later goes back to the draft track; only the affected parts are unlocked.

7. **Write constraints down before creative work.** Every brief carries the hard
   facts, the user's latest corrections, what must not change, and how it will be
   accepted. Every design idea states its purpose, mechanism and why it fits.
   Anything without evidence is labelled "unverified".

8. **Ask the user only for real decisions:** ambiguity that changes the result,
   irreversible choices, subjective acceptance, or anything outside the granted
   scope. Batch these questions and keep working on what does not depend on them.

9. **At most two automatic retries per failure.** Check requirement, context and
   tools first. Keep the best version and the failure evidence; if it still fails,
   report. Move to a stronger model only once you have confirmed reasoning was
   the bottleneck.

10. **Do not expand scope.** No unrequested features, research or refactors. Ask
    before installing packages, MCP servers, plugins or widening permissions.

## Evidence rules

- "Handed back" is not "verified", and "verified" is not "merged". The status file
  uses exactly these states: running, handed back (awaiting check), merged
  (awaiting user), done, returned with reason.
- The orchestrator re-runs the acceptance commands itself. A worker's summary is
  not evidence.
- No claim about fun, ease of use or demand without a human test. See `EVIDENCE_RULES.md`.

## Health check

`tools/health.py` runs on every user message (hook). It is silent when green and
injects a warning plus a required action when not. About every 30 minutes a fresh
Codex session writes a short independent report from a fixed prompt. Relay a
green report in one line; pass a report with recommendations to the user
verbatim and say what you did about each item. Do not edit the report prompt and
do not write the report yourself.

## Context

One session, one milestone. Load tool output and images only as needed. At the
end of a stage, or after repeated failures, save `NOTES.md` and the hand-backs,
then ask the user to `/compact` (the orchestrator cannot run it itself). Never
`/clear` with unsaved results or unreturned workers.

## Review cadence

Review the process only when a milestone completes, the same kind of task fails
twice in a row, or the user rejects a result. Change one thing at a time and
record the reason and the observed effect. Turn a procedure into a skill only
after it has been used three times.
