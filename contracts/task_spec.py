#!/usr/bin/env python3
"""Shared Task Spec validation, stdlib only.

`schema/task-spec.schema.json` is the single source of truth for fields, types and
allowed values. This module applies it with a small validator that covers exactly
the JSON Schema keywords that schema uses. An unsupported keyword is reported as an
error instead of being silently ignored, so the schema cannot grow past what is
actually enforced.

Project-specific inputs, looked up next to this file unless overridden:
    concerns.json    concern registry + which concerns each tier must receive
                     (falls back to concerns.example.json)
    invariants.md    owner invariants, pasted verbatim into every packet
                     (falls back to invariants.example.md)
Override with CONTRACT_CONCERNS / CONTRACT_INVARIANTS environment variables.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA_PATH = HERE / "schema" / "task-spec.schema.json"

TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
    "integer": int,
    "number": (int, float),
}
ANNOTATIONS = {"$schema", "title", "description"}
SUPPORTED = ANNOTATIONS | {
    "type", "enum", "minLength", "pattern", "items", "minItems",
    "uniqueItems", "required", "properties", "additionalProperties",
}


def _pick(env: str, name: str) -> Path:
    if os.environ.get(env):
        return Path(os.environ[env])
    real = HERE / name
    return real if real.exists() else HERE / name.replace(".", ".example.", 1)


def concerns_path() -> Path:
    return _pick("CONTRACT_CONCERNS", "concerns.json")


def invariants_path() -> Path:
    return _pick("CONTRACT_INVARIANTS", "invariants.md")


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def load_registry() -> dict:
    """Return {"concerns": {...}, "tiers": {...}}."""
    return json.loads(concerns_path().read_text(encoding="utf-8"))


def _check(value, schema: dict, where: str, errors: list[str]) -> None:
    unsupported = set(schema) - SUPPORTED
    if unsupported:
        errors.append(f"{where}: schema uses unsupported keyword(s): {', '.join(sorted(unsupported))}")
        return

    t = schema.get("type")
    if t is not None:
        ok = isinstance(value, TYPES[t])
        if t in ("integer", "number") and isinstance(value, bool):
            ok = False
        if not ok:
            errors.append(f"{where}: expected {t}, got {type(value).__name__}")
            return

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{where}: {value!r} is not one of {schema['enum']}")

    if isinstance(value, str):
        # Whitespace-only text counts as empty: "   " is not a mission.
        if len(value.strip()) < schema.get("minLength", 0):
            errors.append(f"{where}: must not be empty")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{where}: {value!r} does not match {schema['pattern']}")

    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{where}: needs at least {schema['minItems']} item(s)")
        if schema.get("uniqueItems") and len(set(map(repr, value))) != len(value):
            errors.append(f"{where}: items must be unique")
        if "items" in schema:
            for i, item in enumerate(value):
                _check(item, schema["items"], f"{where}[{i}]", errors)

    if isinstance(value, dict):
        props = schema.get("properties", {})
        for k in schema.get("required", []):
            if k not in value:
                errors.append(f"{where}: missing field: {k}")
        if schema.get("additionalProperties") is False:
            for k in sorted(set(value) - set(props)):
                errors.append(f"{where}: unknown field: {k}")
        for k, sub in props.items():
            if k in value:
                _check(value[k], sub, f"{where}.{k}" if where != "spec" else k, errors)


def validate_spec(spec, schema: dict | None = None, registry: dict | None = None) -> list[str]:
    """Return human-readable problems; an empty list means the spec is valid."""
    schema = load_schema() if schema is None else schema
    registry = load_registry() if registry is None else registry
    errors: list[str] = []
    _check(spec, schema, "spec", errors)
    if isinstance(spec, dict) and isinstance(spec.get("relevant_concerns"), list):
        known = set(registry["concerns"])
        unknown = sorted({c for c in spec["relevant_concerns"] if isinstance(c, str)} - known)
        if unknown:
            errors.append("unknown concern IDs: " + ", ".join(unknown))
    return errors


def required_concerns(tier: str, registry: dict | None = None) -> list[str]:
    """Concerns the builder injects for a tier, whatever the spec author listed."""
    registry = load_registry() if registry is None else registry
    rule = registry.get("tiers", {}).get(tier, [])
    return sorted(registry["concerns"]) if rule == "all" else list(rule)
