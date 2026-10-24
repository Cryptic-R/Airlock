"""Versioned JSON snapshots for the simulated engine; never deserialize executable objects."""
from contextlib import contextmanager
from dataclasses import fields, is_dataclass
from enum import Enum
import json
import os
from pathlib import Path
import sqlite3
import threading

from .audit import Entry
from .escalation import Escalation
from .gate import BoundAction, Decision, Reason
from .ledger import SessionLedger
from .plan import Arg, Step
from .provenance import Origin, Provenance
from .store import Payment, Record
from .tools import Slot, ToolSpec

TYPES = {c.__name__: c for c in (Entry, Escalation, BoundAction, Reason, SessionLedger,
                                Arg, Step, Provenance, Payment, Record, Slot, ToolSpec)}
ENUMS = {c.__name__: c for c in (Origin, Decision)}


def encode(value):
    if isinstance(value, Enum):
        return {"$enum": type(value).__name__, "value": value.value}
    if is_dataclass(value):
        return {"$type": type(value).__name__, "fields": {f.name: encode(getattr(value, f.name)) for f in fields(value)}}
    if isinstance(value, (set, frozenset, tuple)):
        return {"$sequence": type(value).__name__, "items": [encode(v) for v in value]}
    if isinstance(value, list):
        return [encode(v) for v in value]
    if isinstance(value, dict):
        return {"$dict": [[encode(k), encode(v)] for k, v in value.items()]}
    return value


def decode(value):
    if isinstance(value, list):
        return [decode(v) for v in value]
    if not isinstance(value, dict):
        return value
    if "$enum" in value:
        return ENUMS[value["$enum"]](value["value"])
    if "$type" in value:
        return TYPES[value["$type"]](**{k: decode(v) for k, v in value["fields"].items()})
    if "$sequence" in value:
        return {"set": set, "frozenset": frozenset, "tuple": tuple}[value["$sequence"]](decode(v) for v in value["items"])
    if "$dict" in value:
        return {decode(k): decode(v) for k, v in value["$dict"]}
    raise ValueError("Unknown snapshot encoding")


def dump(lock):
    return json.dumps({"version": 1, "state": encode({
        "store": vars(lock.store), "ledger": vars(lock.ledger),
        "escalations": vars(lock.escalations), "audit": vars(lock.audit),
        "processed": lock.processed,
        "paid_messages": getattr(lock, "paid_messages", {}),
        "paid_invoices": list(getattr(lock, "paid_invoices", set())),
        "message_statuses": getattr(lock, "message_statuses", {}),
        "failed_payments": getattr(lock, "failed_payments", {})})}, allow_nan=False)


def restore(lock, payload):
    data = json.loads(payload)
    if data["version"] != 1:
        raise ValueError("Unsupported persisted state version")
    state = decode(data["state"])
    for key in ("store", "ledger", "escalations", "audit"):
        vars(getattr(lock, key)).update(state[key])
    lock.processed = state.get("processed", {})
    lock.paid_messages = state.get("paid_messages", {})
    invoices = state.get("paid_invoices", [])
    lock.paid_invoices = set(invoices) if isinstance(invoices, (list, set, tuple)) else set()
    lock.message_statuses = state.get("message_statuses", {})
    lock.failed_payments = state.get("failed_payments", {})
    if not lock.audit.verify():
        raise ValueError("Persisted audit chain verification failed")


_mutex = threading.RLock()
_local = threading.local()


@contextmanager
def transaction(user, sessions, factory):
    """Serialize demo mutations and commit complete state atomically, including effects.

    This is safe for simulated local effects only. Real payments require a provider
    idempotency/reconciliation coordinator, not a database snapshot.
    """
    with _mutex:
        if getattr(_local, "active", False):
            yield
            return
        path = Path(os.getenv("AIRLOCK_STATE_DB", "agent_storage/airlock.sqlite3"))
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, timeout=120)
        os.chmod(path, 0o600)
        try:
            conn.execute("CREATE TABLE IF NOT EXISTS sessions (owner TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT payload FROM sessions WHERE owner=?", (user,)).fetchone()
            lock = factory(user)
            if row:
                restore(lock, row[0])
            sessions[user] = lock
            _local.active = True
            yield
            conn.execute("INSERT INTO sessions VALUES (?,?) ON CONFLICT(owner) DO UPDATE SET payload=excluded.payload",
                         (user, dump(sessions[user])))
            conn.commit()
        except BaseException:
            conn.rollback()
            sessions.pop(user, None)
            raise
        finally:
            _local.active = False
            conn.close()
