"""Compare two implementations against independently stored business outcomes."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from workflow import GuardedWorker, NaiveWorker, ProcessStopped, SimulatedOrderService

ROOT = Path(__file__).resolve().parent


def run_case(case, worker_type):
    service = SimulatedOrderService(case["idempotency"], case["faults"])
    statuses = []
    receipts = []
    with TemporaryDirectory(prefix="workflow-demo-") as temp:
        journal = Path(temp) / "operations.sqlite"
        worker = worker_type(service, journal)
        try:
            for event in case["events"]:
                try:
                    result = worker.submit(event["command"],
                                           event.get("stop_after_remote_success", False))
                    statuses.append(result.status)
                    receipts.append(result.order_id)
                except ProcessStopped:
                    statuses.append("process_stopped")
                    receipts.append(None)
                    worker.close()
                    worker = worker_type(service, journal)
        finally:
            worker.close()
    actual = {"statuses": statuses, "orders": service.orders}
    mismatches = [field for field in ("statuses", "orders")
                  if actual[field] != case["expected"][field]]
    return {"passed": not mismatches, "mismatches": mismatches, "actual": actual,
            "receipts": receipts, "remote_calls": service.calls}


def build_report():
    cases = json.loads((ROOT / "cases.json").read_text())
    results = [{"id": case["id"], "name": case["name"], "expected": case["expected"],
                "naive": run_case(case, NaiveWorker),
                "guarded": run_case(case, GuardedWorker)} for case in cases]
    return {
        "kind": "deterministic_synthetic_acceptance_demo",
        "limitations": ["No live API or AI model evaluated", "No customer or revenue validation",
                        "Single worker only", "Provider idempotency never expires in simulation",
                        "Needs-verification is a safe stop, not a completed business transaction"],
        "summary": {"cases": len(results),
                    "naive_passed": sum(r["naive"]["passed"] for r in results),
                    "guarded_passed": sum(r["guarded"]["passed"] for r in results)},
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None,
                        help="Optionally write JSON results to this local file")
    args = parser.parse_args()
    report = build_report()
    if args.output:
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    for row in report["results"]:
        print(f"{row['id']}: naive={'PASS' if row['naive']['passed'] else 'FAIL'}, "
              f"guarded={'PASS' if row['guarded']['passed'] else 'FAIL'}")
    print(json.dumps(report["summary"]))
    return int(report["summary"]["guarded_passed"] != report["summary"]["cases"])


if __name__ == "__main__":
    raise SystemExit(main())
