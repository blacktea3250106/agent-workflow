import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import health  # noqa: E402

BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"


class ProcessCountTests(unittest.TestCase):
    """The cases from the false-positive fix (decisions/2026-10-08-health-false-positive.md)."""

    def count(self, *commands):
        import shlex
        return health.count_processes([shlex.split(c) for c in commands], "Blender", ("-b", "--background"))

    def test_gui_only(self):
        self.assertEqual(self.count(BLENDER), 0)

    def test_one_background_render(self):
        self.assertEqual(self.count(f"{BLENDER} -b --factory-startup -P x.py"), 1)

    def test_two_background_renders(self):
        self.assertEqual(self.count(f"{BLENDER} -b -P a.py", f"{BLENDER} --background -P b.py"), 2)

    def test_shell_mentioning_blender_is_not_a_render(self):
        self.assertEqual(self.count(f"{BLENDER} -b -P a.py", f"zsh -c '{BLENDER} -b -P a.py'"), 1)

    def test_search_tool_mentioning_blender_is_not_a_render(self):
        self.assertEqual(self.count(f"{BLENDER} -b -P a.py", f"ugrep -r 'MacOS/Blender -b' ."), 1)

    def test_codex_exec_only(self):
        import shlex
        table = [shlex.split(c) for c in ("codex exec -s read-only -", "codex login", "node codex exec")]
        self.assertEqual(health.count_processes(table, "codex", subcommand="exec"), 1)


class EvaluateTests(unittest.TestCase):
    BASE = {"context_k": 50, "unanswered": 0, "oldest_wait_s": 0, "slow_replies": 0,
            "oldest_worker_min": 0, "heavy_jobs": 0, "p1_in_progress": 0}

    def colours(self, **changes):
        return [a[0] for a in health.evaluate({**self.BASE, **changes})]

    def test_green_is_silent(self):
        self.assertEqual(self.colours(), [])

    def test_thresholds(self):
        self.assertEqual(self.colours(context_k=130), ["yellow"])
        self.assertEqual(self.colours(context_k=552), ["red"])
        self.assertEqual(self.colours(unanswered=1, oldest_wait_s=100), ["yellow"])
        self.assertEqual(self.colours(unanswered=3, oldest_wait_s=10), ["red"])
        self.assertEqual(self.colours(p1_in_progress=3), ["red"])
        self.assertEqual(self.colours(oldest_worker_min=41), ["red"])
        self.assertEqual(self.colours(heavy_jobs=2), ["red"])


class TranscriptTests(unittest.TestCase):
    def test_unanswered_and_context(self):
        now = time.time()
        stamp = lambda s: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - s))
        rows = [
            {"type": "user", "timestamp": stamp(300), "origin": {"kind": "human"}},
            {"type": "assistant", "timestamp": stamp(290), "message": {
                "usage": {"input_tokens": 10, "cache_read_input_tokens": 150_000},
                "content": [{"type": "text", "text": "on it"}]}},
            {"type": "user", "timestamp": stamp(200), "origin": {"kind": "human"}},
            {"type": "assistant", "timestamp": stamp(100), "message": {
                "content": [{"type": "tool_use", "name": "Bash"}]}},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.jsonl"
            path.write_text("\n".join(json.dumps(r) for r in rows) + "\nnot json\n")
            m = health.session_metrics(path, now)
        self.assertEqual(m["context_k"], 150)
        self.assertEqual(m["unanswered"], 1)            # a tool call is not a reply
        self.assertGreaterEqual(m["oldest_wait_s"], 199)
        self.assertEqual(m["worst_first_reply_s"], 10)


if __name__ == "__main__":
    unittest.main()
