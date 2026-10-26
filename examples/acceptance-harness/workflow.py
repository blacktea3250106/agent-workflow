"""Offline acceptance-test sample. No network, model calls, or customer data."""

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path


class ResponseLost(Exception):
    """The caller cannot tell whether the remote write committed."""


class ProcessStopped(Exception):
    """Test-only stop after remote success but before the local receipt."""


@dataclass(frozen=True)
class Outcome:
    status: str
    order_id: str | None = None


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def valid_command(command):
    if not isinstance(command, dict):
        return False
    if set(command) != {"tenant", "operation", "payload"}:
        return False
    if any(not isinstance(command[k], str) or not command[k].strip()
           for k in ("tenant", "operation")):
        return False
    payload = command["payload"]
    return (isinstance(payload, dict)
            and set(payload) == {"customer", "sku", "quantity"}
            and all(isinstance(payload[k], str) and bool(payload[k].strip())
                    for k in ("customer", "sku"))
            and type(payload["quantity"]) is int
            and 1 <= payload["quantity"] <= 10000)


class SimulatedOrderService:
    """Permissive endpoint with an explicit, idealized idempotency contract.

    Records never expire in this simulation. Actual providers have different
    retention, parameter, error, and concurrency rules. No Stripe API emulation.
    """

    def __init__(self, supports_idempotency=True, faults=()):
        self.supports_idempotency = supports_idempotency
        self.faults = list(faults)
        self.orders = []
        self.receipts = {}
        self.calls = 0

    def create_order(self, command, operation_key=None):
        self.calls += 1
        body = canonical({"tenant": command["tenant"], "payload": command["payload"]})
        key = operation_key if self.supports_idempotency else None
        if key is not None and key in self.receipts:
            original_body, order_id = self.receipts[key]
            if original_body != body:
                raise ValueError("Provider rejected same key with different parameters")
            return order_id
        fault = self.faults.pop(0) if self.faults else None
        if fault == "before_commit":
            raise ResponseLost()
        order_id = f"order-{len(self.orders) + 1}"
        self.orders.append({"tenant": command["tenant"],
                            "payload": json.loads(canonical(command["payload"]))})
        if key is not None:
            self.receipts[key] = (body, order_id)
        if fault == "after_commit":
            raise ResponseLost()
        return order_id


class NaiveWorker:
    """Deliberately weak baseline: no validation, receipt, or idempotency key."""

    def __init__(self, service, journal_path):
        self.service = service

    def submit(self, command, stop_after_remote_success=False):
        for _ in range(2):
            try:
                order_id = self.service.create_order(command)
            except ResponseLost:
                continue
            if stop_after_remote_success:
                raise ProcessStopped()
            return Outcome("confirmed", order_id)
        return Outcome("needs_verification")

    def close(self):
        pass


class GuardedWorker:
    """Single worker, bounded retries, durable local intent and receipt.

    The tenant must be supplied by a trusted authentication layer in a real
    integration. This sample takes fixture input and implements no auth layer.
    """

    def __init__(self, service, journal_path: Path):
        self.service = service
        self.db = sqlite3.connect(journal_path)
        self.db.execute("""CREATE TABLE IF NOT EXISTS operations (
            operation_key TEXT PRIMARY KEY,
            payload_hash TEXT NOT NULL,
            state TEXT NOT NULL,
            order_id TEXT
        )""")
        self.db.commit()

    def submit(self, command, stop_after_remote_success=False):
        if not valid_command(command):
            return Outcome("rejected")
        key = canonical([command["tenant"], command["operation"]])
        fingerprint = hashlib.sha256(canonical(command["payload"]).encode()).hexdigest()
        previous = self.db.execute(
            "SELECT payload_hash, state, order_id FROM operations WHERE operation_key=?",
            (key,)).fetchone()
        if previous:
            if previous[0] != fingerprint:
                return Outcome("key_conflict")
            if previous[1] == "confirmed":
                return Outcome("confirmed", previous[2])
            if not self.service.supports_idempotency:
                return Outcome("needs_verification")
        else:
            # Commit intent before sending. A crash in this gap can require
            # verification even when no remote write happened: safety costs availability.
            with self.db:
                self.db.execute("INSERT INTO operations VALUES (?, ?, 'pending', NULL)",
                                (key, fingerprint))

        attempts = 2 if self.service.supports_idempotency else 1
        for _ in range(attempts):
            try:
                order_id = self.service.create_order(command, operation_key=key)
            except ResponseLost:
                continue
            if stop_after_remote_success:
                raise ProcessStopped()
            with self.db:
                self.db.execute("UPDATE operations SET state='confirmed', order_id=? "
                                "WHERE operation_key=?", (order_id, key))
            return Outcome("confirmed", order_id)
        return Outcome("needs_verification")

    def close(self):
        self.db.close()
