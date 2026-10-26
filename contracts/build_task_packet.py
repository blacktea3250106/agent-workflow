#!/usr/bin/env python3
"""Render the exact prompt a worker receives from a validated Task Spec.

    python3 contracts/build_task_packet.py SPEC.json OUTPUT.md [--registry REGISTRY.jsonl]

The orchestrator decides *what* a worker should do. It does not get to decide
whether the worker hears the owner's fixed requirements: those are injected here
from invariants.md and the concern registry, by tier.

If the spec is invalid, nothing is written and the exit code is non-zero; the rule
is "no valid packet, no spawn". With --registry, one JSON line (task id, tier,
mode, sha256 and size of the rendered prompt) is appended, so you can later prove
which prompt a given worker actually got.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from task_spec import invariants_path, load_registry, required_concerns, validate_spec

HUMAN_VALIDATION = {
    "NOT_VALIDATED": "No human test data exists for this task. Every conclusion about fun, "
                     "usability, comprehension or demand is an AI hypothesis and must be labelled so.",
    "HUMAN_PLAYTEST_PENDING": "A human test is planned but has no data yet. Treat conclusions as AI "
                              "hypotheses and list the questions humans still need to answer.",
    "HUMAN_EVIDENCE_PROVIDED": "Human test data is in the allowed context. Cite it as OBSERVED / "
                               "REPORTED and keep it separate from INFERRED and AI_HYPOTHESIS claims.",
}


def bullets(items) -> str:
    return "\n".join(f"- {x}" for x in items)


def render(spec: dict, registry: dict, invariants: str) -> str:
    wanted = set(spec.get("relevant_concerns", [])) | set(required_concerns(spec["tier"], registry))
    concern_lines = [f"- {cid}: {registry['concerns'][cid]['name']}. {registry['concerns'][cid]['question']}"
                     for cid in sorted(wanted)]
    sections = [
        f"# TASK PACKET: {spec['task_id']}",
        "## Mission\n" + spec["mission"],
        "## Tier / provider / mode\n" + bullets([
            f"Tier: {spec['tier']}",
            f"Preferred provider: {spec.get('provider', 'either')}",
            f"Capability profile: {spec.get('capability_profile', 'chosen at runtime')}",
            f"Independence mode: {spec['independence_mode']}",
        ]),
        "## Decision authority\n" + spec["decision_authority"],
        "## Non-goals\n" + (bullets(spec["non_goals"]) or "- none listed"),
        "## Owner invariants (do not redefine these)\n" + invariants.strip(),
        "## Concern coverage\n" + ("\n".join(concern_lines) or
                                   "- No extended concern set for this low-tier task; owner invariants still apply."),
        "## Allowed context\n" + bullets(spec["allowed_context"]),
        "## Evidence required\n" + bullets(spec["evidence_required"]),
        "## Output contract\n" + spec["output_contract"],
        "## Human validation status\n" + f"- {spec['human_validation_status']}: "
                                          f"{HUMAN_VALIDATION[spec['human_validation_status']]}",
        "## Stop condition\n" + spec["stop_condition"],
        "## Evidence honesty\n" + bullets([
            "Separate OBSERVED / MEASURED facts from INFERRED interpretation.",
            "Never claim human fun, usability, demand or comprehension without human test data in this task.",
            "If a required tool, file or runtime is unavailable, report the missing evidence instead of inventing it.",
        ]),
    ]
    return "\n\n".join(sections) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a task packet from a Task Spec.")
    parser.add_argument("spec", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--registry", type=Path, help="append a JSONL audit line here")
    args = parser.parse_args()

    try:
        spec = json.loads(args.spec.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise SystemExit(f"ERROR: cannot read spec: {error}")
    registry = load_registry()
    problems = validate_spec(spec, registry=registry)
    if problems:
        raise SystemExit("ERROR: invalid task spec, refusing to render:\n  " + "\n  ".join(problems))

    packet = render(spec, registry, invariants_path().read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(packet, encoding="utf-8")

    if args.registry:
        data = packet.encode("utf-8")
        line = {
            "task_id": spec["task_id"], "tier": spec["tier"],
            "provider": spec.get("provider", "either"),
            "independence_mode": spec["independence_mode"],
            "human_validation_status": spec["human_validation_status"],
            "spec": str(args.spec), "prompt": str(args.output),
            "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
            "rendered_at": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        }
        args.registry.parent.mkdir(parents=True, exist_ok=True)
        with args.registry.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(line, ensure_ascii=False) + "\n")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
