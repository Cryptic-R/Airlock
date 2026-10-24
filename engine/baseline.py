"""Behavioural baseline -- a weak signal, deliberately kept weak.

This layer exists to catch the boring anomaly, not to be the thing standing
between an attacker and your money. It is advisory: it can raise an escalation,
it can never authorise one.
"""
from __future__ import annotations

from statistics import median


class Baseline:
    def __init__(self, store) -> None:
        self.store = store

    def check(self, action: str, payee_handle: str | None, amount: float | None):
        notes = []
        if payee_handle:
            hist = self.store.history(payee_handle)
            if amount is not None:
                if not hist:
                    notes.append("first payment ever to this payee")
                else:
                    m = median(hist)
                    if m and amount > 2.0 * m:
                        notes.append(f"{amount / m:.1f}x this payee's usual amount")
                    if m and amount < 0.2 * m:
                        notes.append("unusually small for this payee")
        return notes
