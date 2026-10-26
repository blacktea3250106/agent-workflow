#!/usr/bin/env python3
"""Workflow health check: measure the orchestrator session instead of trusting its own judgement.

    python3 tools/health.py            print the current numbers and any alerts
    python3 tools/health.py --hook     UserPromptSubmit hook: silent when green, warns otherwise
    python3 tools/health.py --report   start an independent Codex review now

What it measures (from the Claude Code session transcript and the process table):
    context_k            current context size of the orchestrator, in thousands of tokens
    unanswered           user messages that have not had a text reply yet
    oldest_wait_s        how long the oldest of those has waited
    worst_first_reply_s  slowest time-to-first-reply in the last 30 minutes
    slow_replies         model turns that took longer than SLOW_REPLY_SECONDS
    workers              sub-agents that wrote to their log in the last 3 minutes
    oldest_worker_min    age of the oldest of those
    codex_workers        running `codex exec` processes
    heavy_jobs           running background jobs that should be serialized (renders etc.)
    p1_in_progress       rows in the status file marked as P1 and in progress

Every run appends one JSON line to tasks/health/metrics.jsonl. The hook never blocks
the user's prompt: any exception exits 0.

About every 30 minutes of activity, the hook starts a *fresh* Codex session with a
fixed prompt (tools/health-review-prompt.md) plus the recent numbers. The
orchestrator never writes that report itself; it only relays it.

The transcript layout (~/.claude/projects/<slug>/<session>.jsonl and a sibling
<session>/subagents/ folder) is what Claude Code wrote in October 2026. If it
changes, session_metrics() and worker_metrics() are the two places to update.
"""
import datetime as dt
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time

REPO = Path(os.environ.get("HEALTH_REPO", Path(__file__).resolve().parent.parent))
HEALTH = REPO / "tasks" / "health"
METRICS = HEALTH / "metrics.jsonl"
PROMPT = REPO / "tools" / "health-review-prompt.md"
STATUS_FILE = REPO / os.environ.get("HEALTH_STATUS_FILE", "NOTES.md")
TAIL_BYTES = 4_000_000
WINDOW = 30 * 60
REPORT_INTERVAL = 30 * 60
REPORT_TIMEOUT = 10 * 60

# (yellow, red). Starting values from the first real session; change them only with a
# decision record that cites the numbers that justified the change.
CONTEXT_K = (120, 180)
WAIT_SECONDS = (90, 180)
UNANSWERED_RED = 3
P1_RED = 3
WORKER_MINUTES = (20, 40)
HEAVY_JOBS_RED = 2
SLOW_REPLY_SECONDS = 120

# Which processes count as a "heavy job". Default: Blender started in background mode.
HEAVY_EXECUTABLE = os.environ.get("HEALTH_HEAVY_EXE", "Blender")
HEAVY_FLAGS = tuple(os.environ.get("HEALTH_HEAVY_FLAGS", "-b,--background").split(","))
# Markers for an in-progress P1 row in the status file's queue table.
P1_MARKERS = tuple(os.environ.get("HEALTH_P1_MARKERS", "P1,in progress").split(","))


def parse_time(text):
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()


def find_transcript(hook_input):
    path = hook_input.get("transcript_path")
    if path and Path(path).exists():
        return Path(path)
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(REPO))
    files = sorted((Path.home() / ".claude" / "projects" / slug).glob("*.jsonl"),
                   key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def read_rows(path):
    """Read the last TAIL_BYTES of a JSONL transcript; skip partial or bad lines."""
    size = path.stat().st_size
    with path.open("rb") as handle:
        if size > TAIL_BYTES:
            handle.seek(size - TAIL_BYTES)
            handle.readline()
        raw = handle.read().decode("utf-8", errors="replace")
    rows = []
    for line in raw.splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def session_metrics(path, now):
    context = 0
    asks, replies, slow = [], [], 0
    previous = None
    for row in read_rows(path):
        stamp = row.get("timestamp")
        if not stamp or row.get("isSidechain"):
            continue
        when = parse_time(stamp)
        kind = row.get("type")
        if kind == "assistant":
            message = row.get("message", {})
            usage = message.get("usage") or {}
            total = sum(usage.get(key, 0) or 0 for key in
                        ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
            if total:
                context = total
            content = message.get("content") or []
            if any(block.get("type") == "text" and block.get("text", "").strip() for block in content):
                replies.append(when)
            if previous and previous[1] == "user" and when - previous[0] > SLOW_REPLY_SECONDS \
                    and now - when < WINDOW:
                slow += 1
            previous = (when, "assistant")
        elif kind == "user":
            if (row.get("origin") or {}).get("kind") == "human":
                asks.append(when)
            previous = (when, "user")
        elif kind == "attachment":
            # Messages the user typed while the agent was busy arrive as queued commands.
            attachment = row.get("attachment") or {}
            if attachment.get("type") == "queued_command" and attachment.get("commandMode") == "prompt":
                asks.append(when)
    asks.sort()
    first_replies, unanswered = [], []
    for asked in asks:
        answer = next((r for r in replies if r >= asked), None)
        if answer is None:
            unanswered.append(asked)
        elif now - asked < WINDOW:
            first_replies.append(answer - asked)
    return {
        "context_k": context // 1000,
        "unanswered": len(unanswered),
        "oldest_wait_s": int(now - unanswered[0]) if unanswered else 0,
        "worst_first_reply_s": int(max(first_replies)) if first_replies else 0,
        "slow_replies": slow,
    }


def worker_metrics(path, now):
    ages = []
    folder = path.with_suffix("") / "subagents"
    if folder.is_dir():
        for log in folder.glob("*.jsonl"):
            stat = log.stat()
            if now - stat.st_mtime < 180:  # still writing = still running
                ages.append(now - getattr(stat, "st_birthtime", stat.st_ctime))
    return {"workers": len(ages), "oldest_worker_min": int(max(ages) // 60) if ages else 0}


def process_table():
    try:
        result = subprocess.run(["ps", "-axo", "pid,command"], capture_output=True, text=True, check=False)
    except OSError:
        return []
    rows = []
    for line in result.stdout.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and parts[0].isdigit() and parts[0] != str(os.getpid()):
            try:
                rows.append(shlex.split(parts[1]))
            except ValueError:
                continue
    return rows


def count_processes(table, executable, flags=(), subcommand=None):
    """Count processes whose argv[0] *is* `executable`.

    The first version grepped the whole command line, so a shell or a search tool
    whose arguments merely mentioned the Blender path counted as a render. That
    produced red alerts for renders that did not exist. Match argv[0] instead.
    """
    count = 0
    for args in table:
        if not args or Path(args[0]).name != executable:
            continue
        if subcommand and (len(args) < 2 or args[1] != subcommand):
            continue
        if flags and not any(arg in flags for arg in args[1:]):
            continue
        count += 1
    return count


def p1_in_progress():
    try:
        text = STATUS_FILE.read_text()
    except OSError:
        return 0
    return sum(1 for line in text.splitlines()
               if line.startswith("|") and all(marker in line for marker in P1_MARKERS))


def level(value, limits):
    return "red" if value >= limits[1] else "yellow" if value >= limits[0] else "green"


def evaluate(n):
    """Return a list of (colour, observation, required action)."""
    alerts = []

    def add(colour, text, action):
        if colour != "green":
            alerts.append((colour, text, action))

    add(level(n["context_k"], CONTEXT_K), f"context {n['context_k']}k",
        "Write current state to the status file and confirm the write, then ask the user to run "
        "/compact. Do not start new dispatches while red.")
    wait = "red" if n["unanswered"] >= UNANSWERED_RED else level(n["oldest_wait_s"], WAIT_SECONDS)
    add(wait if n["unanswered"] else "green",
        f"{n['unanswered']} user message(s) unanswered, oldest {n['oldest_wait_s']}s",
        "Stop tool calls and answer all pending messages in one reply.")
    add("red" if n["p1_in_progress"] >= P1_RED else "green",
        f"{n['p1_in_progress']} P1 items in progress (limit 2)",
        "List them and ask the user which to drop. Do not open another.")
    add(level(n["oldest_worker_min"], WORKER_MINUTES),
        f"oldest worker running {n['oldest_worker_min']} min",
        "Check it once: long job, stuck, or waiting for review? Handle each case; do not just restart it.")
    add("red" if n["heavy_jobs"] >= HEAVY_JOBS_RED else "green",
        f"{n['heavy_jobs']} heavy jobs running at once",
        "Find which job did not go through tools/run_locked.py.")
    add("yellow" if n["slow_replies"] >= 2 else "green",
        f"{n['slow_replies']} model turns over {SLOW_REPLY_SECONDS}s in the last 30 min",
        "Save state and compact, or split the current task smaller.")
    return alerts


def recent_metrics(now):
    if not METRICS.exists():
        return []
    rows = []
    for line in METRICS.read_text().splitlines()[-200:]:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if now - row.get("t", 0) < 2 * WINDOW:
            rows.append(row)
    return rows


def start_report(now):
    """Launch a fresh read-only Codex session with the fixed prompt plus recent numbers."""
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now))
    request = HEALTH / f"request-{stamp}.md"
    output = HEALTH / f"report-{stamp}.md"
    body = PROMPT.read_text() + "\n\n## Recent health numbers (one measurement per line)\n\n```\n"
    body += "\n".join(json.dumps(row, ensure_ascii=False) for row in recent_metrics(now)[-40:])
    body += "\n```\n"
    request.write_text(body)
    model = os.environ.get("HEALTH_CODEX_MODEL")  # unset = the CLI's configured default
    command = ["codex", "exec", "-s", "read-only", "-C", str(REPO), "-o", str(output), "-"]
    if model:
        command[2:2] = ["-m", model]
    try:
        with request.open() as source, (HEALTH / f"report-{stamp}.log").open("w") as log:
            subprocess.Popen(command, stdin=source, stdout=log, stderr=subprocess.STDOUT,
                             start_new_session=True)
    except OSError as error:
        return f"cannot start Codex report: {error}"
    (HEALTH / "report-state.json").write_text(json.dumps({"started": now, "output": str(output)}))
    return None


def report_status(now, allow_start):
    """Return (new report text or None, problem text or None)."""
    state_file = HEALTH / "report-state.json"
    state = json.loads(state_file.read_text()) if state_file.exists() else {}
    text = problem = None
    output = Path(state["output"]) if state.get("output") else None
    if output and not state.get("shown"):
        if output.exists() and output.stat().st_size:
            text = output.read_text().strip()
            state["shown"] = True
            state_file.write_text(json.dumps(state))
        elif now - state.get("started", now) > REPORT_TIMEOUT:
            problem = f"health report not produced {REPORT_TIMEOUT // 60} min after start ({output.name})"
            state["shown"] = True
            state_file.write_text(json.dumps(state))
    due = now - state.get("started", 0) > REPORT_INTERVAL
    active = len([row for row in recent_metrics(now) if now - row["t"] < WINDOW]) >= 2
    if allow_start and due and active and os.environ.get("HEALTH_NO_REPORT") != "1":
        problem = start_report(now) or problem
    return text, problem


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    hook_input = {}
    if mode == "--hook":
        try:
            hook_input = json.load(sys.stdin)
        except ValueError:
            hook_input = {}
    now = time.time()
    HEALTH.mkdir(parents=True, exist_ok=True)
    transcript = find_transcript(hook_input)
    numbers = {"t": int(now), "time": time.strftime("%H:%M:%S", time.localtime(now)),
               "mode": mode or "manual"}
    if transcript:
        numbers.update(session_metrics(transcript, now))
        numbers.update(worker_metrics(transcript, now))
    else:
        numbers.update({"context_k": 0, "unanswered": 0, "oldest_wait_s": 0, "worst_first_reply_s": 0,
                        "slow_replies": 0, "workers": 0, "oldest_worker_min": 0})
    table = process_table()
    numbers["codex_workers"] = count_processes(table, "codex", subcommand="exec")
    numbers["heavy_jobs"] = count_processes(table, HEAVY_EXECUTABLE, HEAVY_FLAGS)
    numbers["p1_in_progress"] = p1_in_progress()
    alerts = evaluate(numbers)
    numbers["status"] = "red" if any(a[0] == "red" for a in alerts) else "yellow" if alerts else "green"
    with METRICS.open("a") as handle:
        handle.write(json.dumps(numbers, ensure_ascii=False) + "\n")

    if mode == "--report":
        print(start_report(now) or "Started a Codex health report in the background; see tasks/health/")
        return 0

    report, problem = report_status(now, allow_start=(mode == "--hook"))
    lines = []
    if alerts or problem:
        lines.append(f"[workflow health: {numbers['status']}] " + "; ".join(a[1] for a in alerts))
        lines += [f"- {colour.upper()} | {text} -> {action}" for colour, text, action in alerts]
        if problem:
            lines.append(f"- RED | {problem} -> tell the user the health report is broken and "
                         "check which Codex model is available.")
    if report:
        lines.append("[independent health report, written by a fresh Codex session] If it says "
                     "'keep', relay one line. If it recommends changes, pass it to the user verbatim "
                     "and report what you did about each item:")
        lines.append(report)
    if mode == "--hook":
        if lines:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                                     "additionalContext": "\n".join(lines)}},
                             ensure_ascii=False))
        return 0
    print(json.dumps(numbers, ensure_ascii=False))
    print("\n".join(lines) if lines else "all green")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:  # A broken health check must never block the user's prompt.
        print(f"health.py failed: {error}", file=sys.stderr)
        sys.exit(0)
