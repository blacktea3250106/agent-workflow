#!/usr/bin/env python3
"""Run one heavy job at a time across a repository and all of its git worktrees.

    python3 tools/run_locked.py -- blender -b scene.blend -P render.py
    python3 tools/run_locked.py --lane gpu -- python3 train.py

Why: several agents working in separate worktrees all share one machine. Without
a lock, five of them start five renders at once and everything slows down.

* The lock key is the repository's *common* git dir, so every worktree of the
  same repo waits on the same lock. Different repos never block each other.
* The child process inherits the lock file descriptor, so the slot stays held
  even if this wrapper is killed while the job is still running.
* Output goes to a log file. Only the exit code, the log path and a short tail
  are printed, so a 500k-character render log never lands in an agent's context.
  On failure the tail is longer and earlier error-looking lines are listed too.

Environment:
    RUN_LOCKED_VERBOSE=1   stream output instead of writing a log
    RUN_LOCKED_LOG_DIR     log folder (default: <main checkout>/tasks/run-logs)
"""
import argparse
import fcntl
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

TAIL_LINES = 20
FAIL_TAIL_LINES = 60
MAX_ERROR_LINES = 20
ERROR_PATTERN = re.compile(r"Traceback|Error|Exception|EXCEPTION|Segmentation|Abort")


def repo_paths(start: Path):
    """Return (checkout root, common git dir). Falls back to `start` outside git."""
    def git(*args):
        result = subprocess.run(["git", "-C", str(start), *args],
                                capture_output=True, text=True, check=False)
        return result.stdout.strip() if result.returncode == 0 else None

    top = git("rev-parse", "--show-toplevel")
    common = git("rev-parse", "--git-common-dir")
    root = Path(top) if top else start
    common_dir = (start / common).resolve() if common else start.resolve()
    return root, common_dir


def lock_path(common: Path, lane: str) -> Path:
    key = hashlib.sha256(f"{common}:{lane}".encode()).hexdigest()[:20]
    return Path(tempfile.gettempdir()) / f"run-locked-{key}.lock"


def log_path(root: Path, common: Path) -> Path:
    if os.environ.get("RUN_LOCKED_LOG_DIR"):
        folder = Path(os.environ["RUN_LOCKED_LOG_DIR"])
    else:
        # Worktrees write into the main checkout so every run is found in one place.
        base = common.parent if common.name == ".git" else root
        folder = base / "tasks" / "run-logs"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / (time.strftime("%Y%m%d-%H%M%S") + f"-{os.getpid()}.log")


def report(path: Path, returncode: int) -> None:
    lines = path.read_text(errors="replace").splitlines()
    print(f"[run] log={path} lines={len(lines)}", file=sys.stderr)
    failed = returncode != 0
    keep = FAIL_TAIL_LINES if failed else TAIL_LINES
    if failed:
        earlier = lines[:max(0, len(lines) - keep)]
        hits = [(n, text) for n, text in enumerate(earlier, 1) if ERROR_PATTERN.search(text)]
        if hits:
            print(f"[run] error lines before the tail ({len(hits)} found):", file=sys.stderr)
            for n, text in hits[:MAX_ERROR_LINES]:
                print(f"{n}: {text}", file=sys.stderr)
    tail = lines[-keep:]
    print(f"[run] last {len(tail)} lines:", file=sys.stderr)
    for text in tail:
        print(text, file=sys.stderr)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run a command under a repo-wide lock.")
    parser.add_argument("--lane", default="default",
                        help="independent lock name, e.g. 'render' or 'gpu' (default: default)")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="-- executable and arguments")
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("provide a command after --")

    root, common = repo_paths(Path.cwd())
    verbose = os.environ.get("RUN_LOCKED_VERBOSE") == "1"
    started = time.monotonic()
    with lock_path(common, args.lane).open("a+") as lock:
        print(f"[run] queued for lane '{args.lane}'", file=sys.stderr, flush=True)
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        print(f"[run] acquired after {time.monotonic() - started:.2f}s", file=sys.stderr, flush=True)
        path = None if verbose else log_path(root, common)
        try:
            if verbose:
                result = subprocess.run(command, pass_fds=(lock.fileno(),), check=False)
            else:
                with path.open("w") as log:
                    result = subprocess.run(command, pass_fds=(lock.fileno(),), check=False,
                                            stdout=log, stderr=subprocess.STDOUT)
        except OSError as error:
            print(f"[run] cannot start command: {error}", file=sys.stderr)
            return 127
        # A negative code means the child died from a signal; map it the way shells do.
        returncode = result.returncode if result.returncode >= 0 else 128 - result.returncode
        if path is not None:
            report(path, returncode)
        print(f"[run] exit={returncode}; total={time.monotonic() - started:.2f}s", file=sys.stderr)
        return returncode


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
