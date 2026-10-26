"""Same checks the original render lock was accepted with: jobs never overlap,
the child's exit code survives, and a failed job releases the lock."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

TOOL = Path(__file__).resolve().parents[1] / "tools" / "run_locked.py"

JOB = """
import sys, time
start = time.time(); time.sleep(0.25); end = time.time()
open(sys.argv[1], "a").write(f"{start} {end}\\n")
sys.exit(int(sys.argv[2]))
"""


class RunLockedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", str(self.dir)], check=True)
        (self.dir / "job.py").write_text(JOB)
        self.env = dict(os.environ, RUN_LOCKED_LOG_DIR=str(self.dir / "logs"))

    def tearDown(self):
        self.tmp.cleanup()

    def start(self, code, lane="test"):
        return subprocess.Popen(
            [sys.executable, str(TOOL), "--lane", lane, "--",
             sys.executable, "job.py", "spans.txt", str(code)],
            cwd=self.dir, env=self.env, stderr=subprocess.PIPE, text=True)

    def spans(self):
        rows = (self.dir / "spans.txt").read_text().split("\n")
        return sorted(tuple(map(float, r.split())) for r in rows if r)

    def test_jobs_do_not_overlap_and_exit_codes_survive(self):
        first, second = self.start(7), self.start(0)
        first.communicate(); second.communicate()
        self.assertEqual({first.returncode, second.returncode}, {7, 0})
        (s1, e1), (s2, e2) = self.spans()
        self.assertLessEqual(e1, s2, "second job started before the first finished")

    def test_failure_releases_lock(self):
        failed = self.start(3); failed.communicate()
        self.assertEqual(failed.returncode, 3)
        began = time.time()
        ok = self.start(0); _, err = ok.communicate(timeout=10)
        self.assertEqual(ok.returncode, 0)
        self.assertLess(time.time() - began, 5)
        self.assertIn("[run] exit=0", err)

    def test_output_goes_to_log_not_caller(self):
        proc = self.start(0); _, err = proc.communicate()
        self.assertIn("[run] log=", err)
        self.assertTrue(list((self.dir / "logs").glob("*.log")))


if __name__ == "__main__":
    unittest.main()
