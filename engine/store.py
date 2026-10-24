"""The trusted store: payees, accounts on file, payment history.

Records are addressed by opaque handles. A plan can name a handle; it can never
name an account number. Resolution happens inside the Actor, after the gate.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .provenance import Provenance, by_record


class UnknownHandle(KeyError):
    pass


@dataclass
class Record:
    handle: str
    kind: str
    data: dict
    prov: Provenance

    @property
    def stained(self) -> bool:
        return not self.prov.trusted


@dataclass
class Payment:
    payee: str
    amount: float
    day: int


class TrustedStore:
    def __init__(self) -> None:
        self._records: dict[str, Record] = {}
        self.payments: list[Payment] = []
        self.reminders: list[dict] = []
        self.drafts: list[dict] = []
        self.sent: list[dict] = []
        self.seeded = 0            # payments present before the agent ran

    # -- writes -----------------------------------------------------------
    def put(self, handle: str, kind: str, data: dict, prov: Provenance | None = None) -> Record:
        rec = Record(handle, kind, dict(data), prov or by_record(handle))
        self._records[handle] = rec
        return rec

    def update(self, handle: str, **data: Any) -> Record:
        rec = self.get(handle)
        rec.data.update(data)
        return rec

    def stain(self, handle: str, refs) -> Record:
        """Mark a record as untrusted-derived. Only a human clears this."""
        rec = self.get(handle)
        rec.prov = rec.prov.stained_by(refs)
        return rec

    def unstain(self, handle: str) -> Record:
        """Restore a record to trusted. Reachable only from a human approval --
        nothing the agent does on its own can call this."""
        rec = self.get(handle)
        rec.prov = by_record(handle)
        return rec

    # -- reads ------------------------------------------------------------
    def get(self, handle: str) -> Record:
        try:
            return self._records[handle]
        except KeyError:
            raise UnknownHandle(handle) from None

    def has(self, handle: str) -> bool:
        return handle in self._records

    def of_kind(self, kind: str) -> list[Record]:
        return [r for r in self._records.values() if r.kind == kind]

    def accounts_for(self, payee_handle: str) -> list[Record]:
        return [r for r in self.of_kind("account") if r.data.get("payee") == payee_handle]

    def history(self, payee_handle: str) -> list[float]:
        return [p.amount for p in self.payments if p.payee == payee_handle]
