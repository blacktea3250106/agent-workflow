# Decision records

Each file records one workflow problem and the fix that was settled on. The rules
themselves live in `playbook/`; this folder records *why* they say what they say.

## How to use

- When the workflow breaks and you settle on a fix, add `YYYY-MM-DD-topic.md`.
- To change a settled fix, do not edit the old file. Add a new one that says what
  changed, why, and which numbers justified it; mark the old item "revised by ...".
- Anything not yet measured in practice is marked **unverified**. Come back and
  fill in the result.
- Raw discussions (other models' reviews) stay in `tasks/`; only conclusions go here.

## Format

- **Problem**: what was observed, with the numbers.
- **Cause**: the verified cause. Mark guesses as guesses.
- **Fix**: what was decided and which file it was written into.
- **Enforced by**: code, or rule only.
- **Status**: unverified / verified / revised.

## Index

| Date | File | Topic |
|---|---|---|
| 2026-10-08 | [2026-10-08-stalls-and-slow-replies.md](2026-10-08-stalls-and-slow-replies.md) | Multi-agent session stalls: eight problems and fixes; revision 1 removes the fixed worker cap |
| 2026-10-08 | [2026-10-08-compact-handoff.md](2026-10-08-compact-handoff.md) | The orchestrator cannot run `/compact`; a hand-over protocol for yellow/red context |
| 2026-10-08 | [2026-10-08-worktree-missing-ignored-assets.md](2026-10-08-worktree-missing-ignored-assets.md) | Workers in worktrees silently rendered placeholders |
| 2026-10-08 | [2026-10-08-health-false-positive.md](2026-10-08-health-false-positive.md) | The health check counted shells that mentioned Blender as renders |
