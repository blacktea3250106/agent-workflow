import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from run_demo import ROOT, run_case
from workflow import GuardedWorker, NaiveWorker, SimulatedOrderService


def command(quantity=2):
    return {"tenant": "A", "operation": "request-1",
            "payload": {"customer": "demo", "sku": "DEMO-1", "quantity": quantity}}


class AcceptanceTests(unittest.TestCase):
    def test_business_outcomes_from_fixtures(self):
        cases = json.loads((ROOT / "cases.json").read_text())
        for case in cases:
            with self.subTest(case=case["id"]):
                result = run_case(case, GuardedWorker)
                self.assertTrue(result["passed"], result)

    def test_duplicate_reuses_original_receipt(self):
        with TemporaryDirectory() as temp:
            remote = SimulatedOrderService(False)
            worker = GuardedWorker(remote, Path(temp) / "journal.sqlite")
            try:
                first = worker.submit(command())
                second = worker.submit(command())
                self.assertEqual(first.order_id, second.order_id)
                self.assertIsNotNone(first.order_id)
                self.assertEqual(remote.calls, 1)
            finally:
                worker.close()

    def test_acknowledged_receipt_survives_worker_recreation(self):
        with TemporaryDirectory() as temp:
            remote = SimulatedOrderService(False)
            journal = Path(temp) / "journal.sqlite"
            worker = GuardedWorker(remote, journal)
            first = worker.submit(command())
            worker.close()
            worker = GuardedWorker(remote, journal)
            try:
                self.assertEqual(worker.submit(command()), first)
                self.assertEqual(remote.calls, 1)
            finally:
                worker.close()

    def test_no_idempotency_does_not_guess_timeout_was_before_commit(self):
        with TemporaryDirectory() as temp:
            remote = SimulatedOrderService(False, ["before_commit"])
            worker = GuardedWorker(remote, Path(temp) / "journal.sqlite")
            try:
                self.assertEqual(worker.submit(command()).status, "needs_verification")
                self.assertEqual(worker.submit(command()).status, "needs_verification")
                self.assertEqual(remote.calls, 1)
                self.assertEqual(remote.orders, [])
            finally:
                worker.close()

    def test_retries_are_bounded_and_pending_operation_can_resume(self):
        with TemporaryDirectory() as temp:
            remote = SimulatedOrderService(True, ["before_commit", "before_commit"])
            worker = GuardedWorker(remote, Path(temp) / "journal.sqlite")
            try:
                self.assertEqual(worker.submit(command()).status, "needs_verification")
                self.assertEqual(remote.calls, 2)
                self.assertEqual(remote.orders, [])
                self.assertEqual(worker.submit(command()).status, "confirmed")
                self.assertEqual(len(remote.orders), 1)
            finally:
                worker.close()

    def test_invalid_quantities_never_reach_remote(self):
        with TemporaryDirectory() as temp:
            remote = SimulatedOrderService(True)
            worker = GuardedWorker(remote, Path(temp) / "journal.sqlite")
            try:
                for quantity in [True, False, 0, -1, 1.5, "2", None, 10001]:
                    with self.subTest(quantity=quantity):
                        self.assertEqual(worker.submit(command(quantity)).status, "rejected")
                self.assertEqual(remote.calls, 0)
            finally:
                worker.close()

    def test_oracle_detects_duplicate_even_when_every_call_reports_success(self):
        case = next(c for c in json.loads((ROOT / "cases.json").read_text())
                    if c["id"] == "duplicate")
        result = run_case(case, NaiveWorker)
        self.assertEqual(result["actual"]["statuses"], ["confirmed", "confirmed"])
        self.assertEqual(result["mismatches"], ["orders"])
        self.assertFalse(result["passed"])


if __name__ == "__main__":
    unittest.main()
