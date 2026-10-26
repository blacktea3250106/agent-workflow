# 2026-10-08: worktrees do not contain git-ignored assets

## Problem

Two Claude workers in separate worktrees updated a scene and handed back frames.
The people in the frames had turned into grey block figures.

## Cause

The character source files lived in an `assets-src/` folder that is git-ignored
(large binaries). `git worktree add` only checks out tracked files, so in the
worktree the asset loader fell back to placeholder geometry. Nothing failed; the
render simply looked wrong.

## Fix

- Short term: symlink the shared asset folder into both worktrees, and mark every
  frame produced before the link as untrustworthy for character quality.
- Rule: every brief lists shared read-only asset paths explicitly, and the worker
  checks they exist before starting. The template says: "Git-ignored files do NOT
  exist in your worktree; if you need one and it is not listed, stop and say so."
- Same lesson for uncommitted work: a worker dispatched before a commit builds on a
  base that does not contain it. `dispatch_codex.sh` warns when the main checkout is dirty.

## Enforced by

Brief template and dispatch script warning. Not enforced by code beyond that.

## Status

Rule adopted the same evening. Whether it prevents a repeat: unverified.
