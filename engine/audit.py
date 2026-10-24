"""Hash-chained audit log.

Append-only in the sense that matters for a demo: every entry commits to the
one before it, so an agent that later gets compromised cannot quietly rewrite
what it did earlier without breaking the chain.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


@dataclass
class Entry:
    seq: int
    kind: str
    payload: dict
    prev: str
    digest: str


class AuditLog:
    def __init__(self) -> None:
        self.entries: list = []

    def append(self, kind: str, payload: dict) -> Entry:
        prev = self.entries[-1].digest if self.entries else "0" * 64
        body = json.dumps({"kind": kind, "payload": payload, "prev": prev},
                          sort_keys=True, default=str)
        digest = hashlib.sha256(body.encode()).hexdigest()
        e = Entry(len(self.entries), kind, payload, prev, digest)
        self.entries.append(e)
        return e

    def verify(self) -> bool:
        prev = "0" * 64
        for e in self.entries:
            body = json.dumps({"kind": e.kind, "payload": e.payload, "prev": prev},
                              sort_keys=True, default=str)
            if hashlib.sha256(body.encode()).hexdigest() != e.digest or e.prev != prev:
                return False
            prev = e.digest
        return True
