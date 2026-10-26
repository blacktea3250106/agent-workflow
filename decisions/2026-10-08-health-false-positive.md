# 2026-10-08: health check reported renders that did not exist

## Problem

Over the first two days the health log had 129 measurements; 12 of them reported 2
or more concurrent renders (red), with a maximum of 4. The lock allows one.

## Cause

The first version counted processes with `pgrep -fl` on the Blender path. Any
process whose *arguments* contained that path matched: a `zsh -c "... Blender ..."`
wrapper, a search tool grepping for "Blender". The wrapper itself had already been
excluded by name, but other shells were not.

## Fix

Parse each process's argv and count it only when `argv[0]`'s basename is the
executable and a background flag (`-b` / `--background`) is present. A Codex
worker made the change in its own worktree (Tier B, write scope: `tools/health.py`
only) and handed back a table:

```
PASS only GUI: expected=0 actual=0
PASS one locked render: expected=1 actual=1
PASS two background renders: expected=2 actual=2
PASS zsh shell mentions Blender: expected=1 actual=1
PASS ugrep mentions Blender: expected=1 actual=1
```

It also reported that its worktree's HEAD was not the SHA in the brief (main had
moved on between writing the brief and dispatching), which the brief asks for.

## Enforced by

Code. `tests/test_health.py` keeps the same cases.

## Lesson

A monitoring tool needs the same verification as the thing it monitors. A false
red teaches people to ignore red.
