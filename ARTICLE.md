# How I run Claude and Codex in parallel with verification gates

*Hao-Fu Chang, October 2026*

In early October I worked on two side projects, using AI agents for most of the
implementation. One was an interactive short film for the web, rendered in Blender
on my laptop. The other was a roguelite game prototype. In both, one Claude Code
session acted as the orchestrator and sent work to Claude sub-agents and to OpenAI's
Codex CLI.

The first long session went badly. This article covers what broke, the numbers I
pulled from the logs afterwards, and the small set of tools and rules I ended up with.
The code is in this repository.

## The setup

The orchestrator is a normal Claude Code session in the project root. It talks to me,
keeps a status file (`NOTES.md`), decides what is on the critical path, writes task
briefs, and dispatches workers:

- **Claude sub-agents** for work that needs judgement, such as scene changes or
  reading a script against the current build.
- **Codex workers**, started with `codex exec` inside their own git worktree,
  pinned to a base commit, for scripts, checkers, audits and diff review.
- **Deterministic tools** for everything that does not need a model.

Each worker gets a brief that lists the exact files it may change, the acceptance
commands, and what to hand back: about ten lines plus paths and a diff. The
orchestrator re-runs the acceptance itself before anything is merged.

## The session that stalled

On 8 October I worked for 144 minutes on the first 15 seconds of the film. By the
end, replies were slow, agents seemed not to start, and I kept asking where things
were stuck. Afterwards I analysed the transcripts of the orchestrator and its 10 sub-agents,
and had Codex and ChatGPT each review the diagnosis once.

The numbers:

- **About 50 messages from me, about 15 of them new requests.** Almost every one
  was started on the spot. Three visual directions were built and then thrown away.
- **34 of my messages queued** while tools were running. The worst single model turn
  took 395 seconds, four more messages queued during it, and the first reply came
  after almost seven minutes.
- **The orchestrator ran Blender in the foreground 71 times** and drove the browser
  84 times. It was the chat window, the dispatcher and the render farm at once.
- **Context went from 86k to 552k tokens** with no compaction. The largest single
  source was about 564,000 characters of Blender terminal output returned through
  tool calls.
- **Up to 7 agents ran at once, and up to 5 Blender processes.** Workers that
  rendered took 39 to 79 minutes. Audit and documentation workers took 4 to 12.
- **Codex got zero tasks.** The CLI's default model was rejected for my account.
  Nobody noticed until 19:53, when an explicit `-m` flag fixed it.
- **About 70% of the changes during the colour pass were structural**: the camera
  angle changed three times, then the carriage length, the passenger layout and the
  view out of the window. Each of those round trips cost minutes to tens of minutes on
  the most expensive version of the scene.

One thing I expected turned out to be false. Agents were not failing to start: all
10 started within one second, with zero errors. Agent startup was fine. The
orchestrator was simply doing too much itself.

## The fixes, in order of how much they mattered

### 1. Keep heavy output out of the context

`tools/run_locked.py` wraps every render. It takes a file lock keyed on the
repository's common git directory, so every worktree of the same repo queues on the
same lock. The child process inherits the lock's file descriptor, so the slot stays
held even if the wrapper is killed. Output goes to a log file. The caller gets the
exit code, the log path and the last 20 lines. On failure it gets 60 lines plus any
earlier lines that look like errors.

It was accepted on three tests (no overlap, exit code preserved, lock released on
failure), kept in `tests/test_run_locked.py`.

### 2. The orchestrator answers first and only controls

These are rules, not code. Answer any interruption before the next tool call.
Run heavy work in the background with one completion watcher. End every reply with one line saying who the ball is with
and what is running. That last rule came from a six-minute stretch where the
orchestrator was waiting on me while I thought it was still working.

### 3. A queue with levels

Every request goes into `NOTES.md` first. P0 (a question, "stop", a change of
direction) gets an immediate answer. P1 is on the current milestone's critical path,
and at most two run at a time. If a third P1 arrives, the orchestrator asks me which
one to drop. P2 is only recorded.

### 4. Measure the session; don't ask it how it is doing

This is the part I would keep if I could keep only one. Things got worse gradually.
No single event triggered a review, and a slow orchestrator is the party least
likely to notice it is slow.

`tools/health.py` runs from a Claude Code `UserPromptSubmit` hook on every message
I send. It reads the session transcript and measures context size, unanswered
messages and how long they have waited, time to first reply, sub-agent age, running
`codex exec` processes, background renders, and in-progress P1 rows in `NOTES.md`.
Green is silent. Anything else injects a warning and a required action into the
conversation: "context red: save NOTES.md, confirm the write, ask the user to
compact, stop dispatching".

About every 30 minutes the hook also starts a fresh, read-only Codex session with
a fixed prompt and the recent numbers. The orchestrator is not allowed to edit that
prompt or write the report itself. It relays a green report in one line and passes
anything else to me verbatim.

Run against the stalled session's transcript, the script read 552k and went red.
Over the next two days it logged 129 measurements: 78 green, 20 yellow, 31 red. The
ten Codex reports were more useful than I expected. The most common finding was
that `NOTES.md` disagreed with reality: the file said two P1 tasks were running
while the process table showed zero workers, or tasks that had come back were still
listed as "running". One report caught a message of mine that had gone unanswered
for 2,343 seconds. Before this, stale state was only noticed when I got confused.

### 5. Remove the worker cap, keep three conditions

My first fix capped parallelism at two implementers plus one read-only worker. I
asked why, and the honest answer was that it was a guess. The seven concurrent
agents earlier were slow for specific reasons: several were rendering at once, their
long reports flooded the orchestrator (context 397k to 531k), and my messages
queued behind them. The number of agents was not the cause.

So the cap went away. A worker can start if it renders only through the lock, its
write scope does not overlap anyone else's (one writer per file), and its hand-back
fits in about ten lines. Slowing down is decided by the health numbers (oldest
worker age, my wait time, context), not by a fixed count. I wrote that as a
revision in the decision record and marked it unverified until I have numbers from
a later session.

### 6. Decide structure on the cheap version

A greybox track now covers the whole film without colour, with a burned-in
timecode. Camera, timing and layout changes happen there. A section moves to the
expensive colour track only when I explicitly say "lock this one".

## What the gates caught

The game prototype used a stricter version of the same idea. Every important task
was written as a JSON Task Spec and rendered into a prompt by
`contracts/build_task_packet.py`. The script validates the spec against a schema,
pastes the owner's fixed requirements in verbatim, adds the design concerns the
task's tier must see, and records the prompt's sha256. If validation fails, no agent
is spawned. That iteration used 10 agent runs, against a soft cap of 16 and a hard cap
of 32.

Three things the gates caught:

**Two models agreeing was not enough.** I ran two blind proposals for the core
mechanic, one from Codex (216 seconds) and one from a Claude sub-agent (51.6 minutes,
223k tokens). Both passed most of the automated metrics. Both also had pieces that
attacked enemies directly, which broke a requirement I had written down. The
invariants were in both prompts, so the check against them was mechanical. Both were
disqualified.

**The verifier found that the evidence was stale.** A fresh Claude verifier was
told to compute the numbers itself before reading the author's summary. It found
that the evidence files on disk came from a build with a cycle cap of 8, while the
shipped build, its rule text and the play instructions all said 6. Against the real
build, 96, 32 and 12 fields differed across the three files. It also found that the
unit tests let 14 of 17 deliberately introduced bugs (mutants) survive, that the rule
text and the engine disagreed in 14 places, and that one "pass" depended on a
tie-break in enumeration order. The author was the orchestrator, so this was the
system checking its own work, and the check was needed.

**The human overruled the metrics.** One build passed most of its AI-measured
criteria. I played it and said it looked like a game with one optimal answer and that
I could not tell what I was supposed to be doing. That build was dropped. The rule
since then is that every stage leaves a build I can start with one command, that my
notes outrank any AI review, and that every spec declares `NOT_VALIDATED`,
`HUMAN_PLAYTEST_PENDING` or `HUMAN_EVIDENCE_PROVIDED`. The current build has
exhaustive search over 108,384 programs behind it, and its status is still
`NOT_VALIDATED`, because nobody except me has played it.

## Things that broke after the fixes

**Worktrees do not contain ignored files.** Two Claude workers handed back frames
where every person had become a grey block figure. The character files lived in a
git-ignored asset folder, and `git worktree add` only checks out tracked files, so the
loader fell back to placeholders without any error. Every brief now lists shared
read-only asset paths, and the dispatch script warns if the main checkout has
uncommitted changes the worker will not see.

**The health check had a false positive.** It counted Blender renders with
`pgrep -f`, so a shell or a search tool whose arguments mentioned the Blender path
counted as a render. Twelve measurements reported two or more concurrent renders,
up to four, while the lock allows one. A Codex worker, allowed to change one file, fixed it by matching `argv[0]`
plus the background flag and handed back a five-row pass table. It also reported,
as the brief requires, that its HEAD was not the SHA in the brief because main had
moved. A false red teaches you to ignore red, so the monitor needs tests too.

**The orchestrator cannot compact itself.** `/compact` is something only the user can
type. The orchestrator sat at 188k to 193k tokens while I asked "can't you compact
yourself?" The protocol now: at yellow, update `NOTES.md` and end the reply with a
fixed line asking me to compact. At red, stop dispatching first. After compaction,
the first action is to read `NOTES.md`. The first manual compaction went from 553,549
tokens to 10,321 in 77 seconds.

## Lessons

1. **Measure the orchestrator from the outside.** Its own sense of progress is the
   least reliable signal in the system. A transcript and a process table are cheap
   and honest.
2. **Most slowness was context, not compute.** Logs, long reports and screenshots
   piling into one session did more damage than the number of agents.
3. **Track "handed back", "verified" and "merged" as three separate states.**
   Most bad surprises came from treating one as another.
4. **Two models agreeing is weak evidence.** Running code, a verifier that computes
   the numbers before reading the author's summary, and a human playing the build are
   the evidence that counts.
5. **Write down why each rule exists.** Every rule in this repo links to a decision
   record with the numbers that caused it and a status. When I wanted to remove the
   worker cap, the record showed that the cap had no evidence behind it.
6. **Do not claim a speed-up you have not measured.** I have not measured one. The
   next session's numbers (time to first reply, rework count, render time) will
   tell me whether these rules helped.

The tools are small: about 360 lines for the health check, 130 for the lock and
350 for the contracts, all Python standard library. The decision records took more
thought than the code.
