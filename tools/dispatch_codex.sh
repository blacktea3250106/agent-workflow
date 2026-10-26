#!/usr/bin/env bash
# Dispatch one Codex worker into its own git worktree, pinned to the current HEAD.
#
#   tools/dispatch_codex.sh <task-id> [model]
#
# Expects the task brief at tasks/<task-id>.md (see contracts/templates/task-brief.md).
# Writes the worker's final message to tasks/<task-id>.result.md and its full
# output to tasks/<task-id>.log. Run it in the background and wait for it to exit;
# the exit is the only completion signal, so there is nothing to poll.
#
# What the orchestrator does afterwards (not automated on purpose):
#   1. git -C "$WT" diff --stat and check that only the files allowed by the brief changed
#   2. re-run the acceptance commands from the brief itself
#   3. commit in the worktree, cherry-pick onto the main branch, then
#      git worktree remove "$WT" (no --force: a dirty worktree means unfinished work)
set -euo pipefail

TASK_ID="${1:?usage: dispatch_codex.sh <task-id> [model]}"
TASK_MODEL="${2:-${CODEX_MODEL:-}}"

if [[ ! "$TASK_ID" =~ ^[A-Za-z0-9-]+$ ]]; then
  echo "task-id must be letters, digits and hyphens only" >&2; exit 2
fi

ROOT=$(git rev-parse --show-toplevel)
BASE=$(git rev-parse --verify HEAD)        # fails on a repo with no commits
BRIEF="$ROOT/tasks/$TASK_ID.md"
WT="${ROOT}-wt/${TASK_ID}"

[[ -f "$BRIEF" ]] || { echo "missing brief: $BRIEF" >&2; exit 2; }
[[ -e "$WT" ]] && { echo "worktree already exists, pick a new task-id: $WT" >&2; exit 2; }

if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  # Uncommitted changes do not exist in the worktree. Say so instead of letting
  # the worker build on a base that is missing them.
  echo "warning: main checkout has uncommitted changes; the worker will not see them" >&2
fi

git worktree add -q -b "task/$TASK_ID" "$WT" "$BASE"
test "$(git -C "$WT" rev-parse HEAD)" = "$BASE"

MODEL_ARGS=()
[[ -n "$TASK_MODEL" ]] && MODEL_ARGS=(-m "$TASK_MODEL")

echo "dispatched $TASK_ID base=$BASE worktree=$WT started=$(date -u +%FT%TZ)"
status=0
codex exec "${MODEL_ARGS[@]+"${MODEL_ARGS[@]}"}" -s workspace-write -C "$WT" \
  -o "$ROOT/tasks/$TASK_ID.result.md" - < "$BRIEF" > "$ROOT/tasks/$TASK_ID.log" 2>&1 || status=$?
echo "returned $TASK_ID exit=$status finished=$(date -u +%FT%TZ)"
exit $status
