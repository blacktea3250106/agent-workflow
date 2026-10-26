# Acceptance harness: check the business outcome, not the API status

A small offline example of the evidence rule applied to an automated workflow.
An upstream step (an LLM agent, an n8n flow, anything) decides to create an
order. The question is not "did every call return 200?" but "does the remote
system end up with exactly the orders it should?"

Python 3.10+ standard library only. No network, no model calls, no real data.

```sh
python3 run_demo.py                  # compare both workers on all cases
python3 run_demo.py --output report.json
python3 -m unittest -v
```

## Files

- `cases.json`: ten hand-written failure cases. Expected statuses *and* the final
  order list are stored separately from the code under test.
- `workflow.py`: a simulated order service with injectable faults; a deliberately
  unprotected `NaiveWorker`; and a `GuardedWorker` with input validation, a durable
  SQLite intent/receipt journal, idempotency keys scoped by tenant, and bounded retries.
- `run_demo.py`: runs both workers against every case and exits non-zero if the
  guarded worker misses any expected outcome.
- `test_workflow.py`: seven tests, including one that proves the oracle catches a
  duplicate order even when every call reported success.

## Result (2026-09-21, re-run 2026-10-26)

Guarded worker: 10/10 cases match. Naive baseline: 2/10. 7/7 unit tests pass.

The baseline is weak on purpose. This does not say anything about any real
platform. Ten passing cases mean those ten pre-written outcomes hold, nothing more.

## Design notes

- The same business request must reuse the same `operation` ID. Resending the same
  order under a new ID can still duplicate it; the harness does not guess sameness
  from content.
- If the provider supports idempotency keys, retries are safe under its rules.
  If it does not and the outcome is unknown, the guarded worker returns
  `needs_verification` and pauses that operation. That is a safe stop, not a
  completed order, and it can trigger even when nothing was written: safety costs
  some availability.
- Invalid input is rejected before any side effect, so the same ID can be reused
  after correction. Reusing an ID with different content is rejected.

## Limits

Single worker, sequential. Not tested: concurrent processes, disk corruption,
deploy upgrades, retention, multi-step inventory/payment consistency, real
provider retention windows. The restart test recreates the local worker while
keeping the simulated remote state; it is not a power-loss test.
