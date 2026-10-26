import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "contracts"))
from task_spec import load_registry, required_concerns, validate_spec  # noqa: E402

TEMPLATES = sorted((ROOT / "contracts" / "templates").glob("*.json"))


class ContractTests(unittest.TestCase):
    def test_templates_are_valid(self):
        self.assertTrue(TEMPLATES)
        for path in TEMPLATES:
            with self.subTest(path=path.name):
                self.assertEqual(validate_spec(json.loads(path.read_text())), [])

    def test_rejects_missing_unknown_and_blank_fields(self):
        spec = json.loads(TEMPLATES[0].read_text())
        spec.pop("stop_condition")
        spec["mision"] = "typo"
        spec["mission"] = "   "
        spec["relevant_concerns"] = ["C01", "C99"]
        problems = "\n".join(validate_spec(spec))
        for expected in ("missing field: stop_condition", "unknown field: mision",
                         "mission: must not be empty", "unknown concern IDs: C99"):
            self.assertIn(expected, problems)

    def test_tier_S_gets_every_concern(self):
        registry = load_registry()
        self.assertEqual(required_concerns("S", registry), sorted(registry["concerns"]))
        self.assertEqual(required_concerns("C", registry), [])

    def test_builder_injects_and_registers(self):
        spec = json.loads((ROOT / "contracts/templates/spec-tier-B-implement.json").read_text())
        self.assertNotIn("relevant_concerns", spec)
        with tempfile.TemporaryDirectory() as tmp:
            out, reg = Path(tmp) / "p.md", Path(tmp) / "reg.jsonl"
            subprocess.run([sys.executable, str(ROOT / "contracts/build_task_packet.py"),
                            str(ROOT / "contracts/templates/spec-tier-B-implement.json"),
                            str(out), "--registry", str(reg)], check=True, capture_output=True)
            packet = out.read_text()
            self.assertIn("C09:", packet)            # injected by tier B
            self.assertIn("C10:", packet)
            self.assertIn("INV-06", packet)          # invariants pasted verbatim
            line = json.loads(reg.read_text())
            self.assertEqual(line["sha256"], hashlib.sha256(packet.encode()).hexdigest())

    def test_builder_refuses_invalid_spec(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text(json.dumps({"task_id": "x", "tier": "S"}))
            out = Path(tmp) / "p.md"
            result = subprocess.run([sys.executable, str(ROOT / "contracts/build_task_packet.py"),
                                     str(bad), str(out)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
