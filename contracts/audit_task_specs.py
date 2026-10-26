#!/usr/bin/env python3
"""Audit Task Specs against the schema and the concern registry.

    python3 contracts/audit_task_specs.py SPEC.json [SPEC.json ...]
    python3 contracts/audit_task_specs.py            # every *.json in tasks/specs/

Exit code 1 if any spec is invalid. A spec that omits concerns its tier requires
only gets a warning, because build_task_packet.py injects them anyway; the warning
tells you the spec author did not think about them.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from task_spec import load_registry, load_schema, required_concerns, validate_spec


def main(argv: list[str]) -> int:
    if any(a in ("-h", "--help") for a in argv):
        print(__doc__.strip())
        return 0
    paths = [Path(p) for p in argv] or sorted(Path("tasks/specs").glob("*.json"))
    schema, registry = load_schema(), load_registry()
    errors = []
    for path in paths:
        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            errors.append(f"{path}: invalid json: {error}")
            continue
        problems = validate_spec(spec, schema, registry)
        errors.extend(f"{path}: {msg}" for msg in problems)
        if problems:
            continue
        missing = sorted(set(required_concerns(spec["tier"], registry)) - set(spec.get("relevant_concerns", [])))
        if missing:
            print(f"WARN {path}: tier {spec['tier']} spec omits {missing}; the builder will inject them.")
    if errors:
        print("\n".join("ERROR " + e for e in errors))
        return 1
    print(f"Audited {len(paths)} task spec(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
