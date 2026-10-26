# 2026-10-08: stalls, slow replies, and work being redone

## Context

A 144-minute session (17:33–19:57 local) on the first 15 seconds of an animated
sequence. The user's experience: the further it went, the slower it got, agents
"would not start", replies took longer and longer, and Codex was not doing anything.

The numbers below come from the transcripts of the orchestrator and its 10
sub-agents. The diagnosis and the plan were each reviewed once by Codex and once
by ChatGPT, independently.

Conclusion first: agents were not failing to start (10 of 10 started within one
second, zero errors). The orchestrator was acting as chat window, dispatcher and
heavy-job runner at the same time, and every new request was started immediately.

## 1. Render output filled the context

- **Problem**: Blender terminal output returned through tool calls was about 564k
  characters, the single largest source. Orchestrator context grew from 86k to
  552k tokens with no compaction.
- **Cause**: the render tool only handled queueing; output streamed straight back.
- **Fix**: the locked runner (`tools/run_locked.py`) writes output to a log file and
  returns the exit code, the log path and the last 20 lines; 60 lines plus earlier
  error lines on failure.
- **Enforced by**: code.
- **Status**: tested for success, failure and queueing. Measured effect on context: unverified.

## 2. User messages queued behind tools and long thinking

- **Problem**: 34 messages arrived while work was running. The worst single model
  turn was 395 s; 4 more messages queued during it, and the first reply came after
  almost 7 minutes.
- **Cause**: the orchestrator itself ran Blender in the foreground 71 times and
  drove the browser 84 times.
- **Fix**: the orchestrator only controls (answer, prioritize, dispatch, verify,
  edits of a few minutes). Heavy jobs always run in the background. Rule 1.
- **Enforced by**: rule only.
- **Known gap**: during a long model turn, every warning arrives late. The only
  real preemption the user has is the interrupt key.

## 3. Every new request started immediately

- **Problem**: about 50 messages and about 15 new requests in 144 minutes, almost
  all started on the spot. Three visual directions were built and then withdrawn.
- **Cause**: no intake levels and no limit on concurrent work.
- **Fix**: P0 / P1 / P2 queue in `NOTES.md`; at most 2 P1 in progress. Rule 2.
- **Enforced by**: rule; `health.py` counts in-progress P1 rows and goes red at 3.

## 4. Nobody knew who had the ball

- **Problem**: for six minutes the orchestrator was waiting on the user while the
  user thought it was still working and asked where it was stuck.
- **Fix**: every reply ends with one line: who we are waiting for, what runs in the background.
- **Enforced by**: rule only.

## 5. Changes happened on the expensive version

- **Problem**: about 70% of changes during the colour pass were structural (camera
  changed three times, carriage length, passenger layout, window content). Each
  round trip took minutes to tens of minutes.
- **Cause**: the cheap draft was treated as an appendix to the colour version.
- **Fix**: two-track review. Structure is locked on the draft; only locked sections
  go to colour. `DISPATCH.md` section 4.
- **Enforced by**: rule only.

## 6. Degradation was only noticed when the user felt it

- **Problem**: things got worse gradually; no single event triggered a review, and
  a slowed-down orchestrator is the least likely party to notice.
- **Fix**: `tools/health.py` measures the session from its transcript on every
  user message; a fresh Codex session writes an independent report every ~30
  minutes from a fixed prompt. The orchestrator does not grade itself.
- **Enforced by**: measurement and triggering are code; acting on a red light is
  still up to the orchestrator.
- **Status**: replaying the stalled session's transcript reads 552k, red.

## 7. Codex got zero tasks

- **Problem**: 0 dispatches to Codex in the whole session.
- **Cause**: the CLI's default model was rejected for this account. Found at
  19:53; explicitly passing a supported model worked.
- **Conclusion**: lost capacity, not the cause of the slowdown.
- **Fix**: non-render work (web layer, tool scripts, checkers, doc sync, audits,
  diff review) goes to Codex first when it fits. The health report is always
  written by Codex. Pin the model and smoke-test it.

## 8. Agents slowing each other down

- **Problem**: 6 agents opened within 3 minutes (7 concurrent); up to 5 Blender
  processes at once. Workers that rendered took 39–79 minutes; audit or doc
  workers took 4–12 minutes.
- **Cause**: one laptop (8-core, 16 GB) is the only render resource. CPU and
  memory pressure were never measured, so "contention" is strongly suspected, not proven.
- **Fix**: the lock guarantees one heavy job at a time (code). Worker count: see revision 1.

## Revision 1: no fixed worker cap (same day, user request)

- **User's question**: why at most "2 implementers + 1 read-only"? Can't 7 run?
- **Checked**: they can. Last time 7 started within a second with no errors. The
  2+1 cap was a conservative guess with no measurement behind it.
- **Why 7 was slow last time**: several of them rendered at once, long hand-backs
  flowed into the orchestrator (context 397k -> 531k), and user messages queued.
  Not the number of agents itself.
- **Changed to**: no cap. A worker may be dispatched when it does not render
  outside the lock, its write scope does not overlap, and its hand-back is ~10
  lines. Slow down based on health numbers, not a count.
- **Status**: unverified. If measurements show many workers hurt reply time or
  hand-back quality, add a cap back and record it here.

## Explicitly not doing

- Layers of manager agents, scheduled architecture-review agents, an always-on
  dispatcher service.
- Dynamic priority algorithms or automatic model-tier switching.
- Two queues or two sets of agents.

## Numbers to track

- Time from a user message to the first useful reply (`worst_first_reply_s`).
- Time from a confirmed request to something the user can accept, and rework count.
