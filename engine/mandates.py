"""Standing mandates: the only source of autonomy in the system.

A mandate is authored by the user, not inferred by a model. It is the answer to
"what is the agent allowed to do while nobody is watching", and it is written
in terms of trusted state: which payees, which accounts, what ceiling, what
variance from the payee's own history.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median


@dataclass
class Envelope:
    """User-authored bounds on a value the agent lifts out of a document."""
    ceiling: float
    variance: float = 0.35   # fraction above the payee's rolling median

    def admits(self, value: float, history: list) -> tuple:
        if value > self.ceiling:
            return False, f"{value:,.2f} is over your {self.ceiling:,.2f} ceiling"
        if history:
            m = median(history)
            limit = m * (1 + self.variance)
            if value > limit:
                return False, (
                    f"{value:,.2f} is {value / m:.1f}x the usual {m:,.2f} "
                    f"for this payee"
                )
        return True, ""


@dataclass
class Mandate:
    name: str
    actions: set
    payees: set = field(default_factory=set)   # empty = any payee
    envelopes: dict = field(default_factory=dict)  # slot name -> Envelope
    allow_irreversible: bool = False

    def covers_action(self, action: str) -> bool:
        return action in self.actions


class MandateSet:
    def __init__(self, mandates: list) -> None:
        self.mandates = mandates

    def for_action(self, action: str, payee_handle: str | None) -> "Mandate | None":
        for m in self.mandates:
            if not m.covers_action(action):
                continue
            if m.payees and payee_handle not in m.payees:
                continue
            return m
        return None
