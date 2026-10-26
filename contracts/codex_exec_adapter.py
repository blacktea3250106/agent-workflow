#!/usr/bin/env python3
"""Run one rendered task packet through `codex exec` and keep everything it produced.

    python3 contracts/codex_exec_adapter.py PROMPT.md RUN_DIR

It deliberately does NOT pass --full-auto, a sandbox mode, an approval policy, a
model or network flags. Those stay under the user's own Codex configuration; a
wrapper should not quietly widen what an agent is allowed to do.

RUN_DIR receives: codex-version.txt, codex-exec-help.txt (preflight, so a CLI
change shows up as a readable failure instead of a silent no-op), stdout.jsonl,
stderr.txt and run.json (exit code, duration).
"""
import json
from pathlib import Path
import subprocess
import sys
import time


def run(args, stdin=None, timeout=None):
    return subprocess.run(args, input=stdin, text=True, capture_output=True, timeout=timeout, check=False)


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: codex_exec_adapter.py PROMPT.md RUN_DIR")
    prompt_path = Path(sys.argv[1]).resolve()
    run_dir = Path(sys.argv[2]).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    prompt = prompt_path.read_text(encoding="utf-8")

    version = run(["codex", "--version"], timeout=30)
    help_text = run(["codex", "exec", "--help"], timeout=30)
    (run_dir / "codex-version.txt").write_text(version.stdout + version.stderr, encoding="utf-8")
    (run_dir / "codex-exec-help.txt").write_text(help_text.stdout + help_text.stderr, encoding="utf-8")
    if version.returncode != 0 or help_text.returncode != 0:
        raise SystemExit("Codex preflight failed; see the run directory.")

    started = time.time()
    result = run(["codex", "exec", "--json", "-"], stdin=prompt)
    (run_dir / "stdout.jsonl").write_text(result.stdout, encoding="utf-8")
    (run_dir / "stderr.txt").write_text(result.stderr, encoding="utf-8")
    meta = {
        "prompt": str(prompt_path),
        "exit_code": result.returncode,
        "duration_seconds": round(time.time() - started, 3),
        "note": "Sandbox, approval and model came from the user's Codex config; this adapter did not override them.",
    }
    (run_dir / "run.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
