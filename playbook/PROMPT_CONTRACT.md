# Prompt contract

The question this answers: when the orchestrator writes prompts for other agents,
how do you make sure it never drops the things the owner cares about?

## Two layers

- **Capability prompt** (`.claude/agents/*.md`, `.codex/agents/*.toml`): long-lived
  stance only, e.g. "red team", "evidence verifier". No project plan in here.
- **Task prompt**: generated per task. The orchestrator decides *what the worker
  should do*. It does not decide *whether the worker hears the owner's
  requirements*. For any important task it writes a Task Spec and renders it:

```text
Task Spec (JSON)
  -> validate against schema/task-spec.schema.json   (fail = no spawn)
  -> inject owner invariants (verbatim)
  -> inject the concerns this tier must receive
  -> render the packet
  -> append sha256 + size to the prompt registry
  -> spawn Claude / call Codex with exactly that file
```

```sh
python3 contracts/audit_task_specs.py tasks/specs/*.json
python3 contracts/build_task_packet.py tasks/specs/X.json tasks/prompts/X.md --registry tasks/prompts/REGISTRY.jsonl
python3 contracts/codex_exec_adapter.py tasks/prompts/X.md tasks/runs/X
```

## Required fields

`task_id`, `tier`, `mission`, `decision_authority`, `non_goals`,
`independence_mode`, `allowed_context`, `evidence_required` (at least one),
`output_contract`, `stop_condition`, `human_validation_status`. Unknown fields are
rejected, so a typo cannot silently drop a field.

## Tiers

Spend on leverage, not evenly.

| Tier | Typical work | What it gets |
|---|---|---|
| S | core mechanic, key architecture, signature feature | all concerns; fresh context; a challenger from the other provider when available; executable evidence |
| A | UX flow, economy, onboarding, technical architecture | relevant concerns plus a fixed base set; one owner plus an independent reviewer |
| B | normal implementation | invariants plus explainability and evidence concerns; one strong worker plus automated tests |
| C | mechanical work | invariants plus an exact contract; prefer a script |

## Independence modes

- `BLIND_PROPOSAL`: cannot see competing proposals, the orchestrator's preference
  or a previous winner. For alternatives on a key decision.
- `BLIND_CHALLENGE`: sees the candidate and the original criteria, not the author's
  defence. The job is to find counter-examples.
- `IMPLEMENT`: sees the locked design, the contract and the relevant code; can write.
- `VERIFY`: sees the original requirement, the candidate and the tests. Does not
  read the author's "done" summary first.
- `SYNTHESIZE`: only after the independent outputs are sealed; proposes the next
  smallest experiment.
- `NORMAL`: research and similar work where independence does not matter.

## Claude and Codex

Claude Code is the control plane. Codex is a worker, challenger, reviewer or bug
hunter, never a second orchestrator. Two providers are worth paying for on a core
decision, a key architecture choice, cross-provider review of a core system, a bug
with no clear root cause, or exploit search. They are not worth it for moving
files, formatting, small bugs with a regression test, or routine builds.

Two models agreeing is not evidence that users will like something. They can be
wrong together. Convergence comes from running prototypes, deterministic tests,
simulation, fresh adversarial review and human tests.

If Codex is unavailable, use two fresh Claude contexts with different framing and
record `provider_diversity: unavailable`. Never pretend a cross-model check happened.

## What prompts cannot enforce

Rules that must hold (no secrets in logs, no writes outside the worktree) belong
in tool permissions, sandboxes, hooks and repo policy. A sentence saying "do not"
is not a control.
