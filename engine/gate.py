"""The gate.

Deterministic code. It reads capability declarations, argument provenance and
the session ledger. It does not read the planner's reasoning, the email, or any
natural language at all, so there is nothing in here for a payload to talk to.

The invariant it enforces:

    Untrusted content may decide *whether* an action happens.
    It may never decide *what* the action does, unless the user wrote down a
    bound in advance and the value falls inside it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .plan import Step
from .provenance import Provenance
from .store import TrustedStore, UnknownHandle
from .tools import REGISTRY, ToolSpec


class Decision(str, Enum):
    ALLOW = "ALLOW"
    ESCALATE = "ESCALATE"
    BLOCK = "BLOCK"


_RANK = {Decision.ALLOW: 0, Decision.ESCALATE: 1, Decision.BLOCK: 2}


@dataclass(frozen=True)
class Reason:
    code: str
    layer: str
    decision: Decision
    text: str          # written for the human who gets the escalation


@dataclass
class BoundAction:
    step: Step
    spec: ToolSpec
    resolved: dict = field(default_factory=dict)   # slot -> Record
    effective: dict = field(default_factory=dict)  # slot -> Provenance
    payee_handle: str | None = None
    amount: float | None = None

    @property
    def privileged(self) -> bool:
        return self.spec.sensitive or self.spec.external or self.spec.irreversible

    def describe(self) -> str:
        def clip(t, n=44):
            t = " ".join(str(t).split())
            return t if len(t) <= n else t[: n - 1] + "\u2026"
        parts = [f"{k}={clip(v.render())}" for k, v in self.step.args.items()]
        return f"{self.step.action}({', '.join(parts)})"


class BindError(Exception):
    pass


def bind(step: Step, store: TrustedStore) -> BoundAction:
    """Resolve handles and compute each argument's effective provenance.

    A record that was written while the session carried untrusted content is
    stained, and the stain is inherited here. That is what stops an attack
    split across two messages: the first message plants, the second message
    tries to spend, and the planted record is still marked.
    """
    spec = REGISTRY[step.action]
    ba = BoundAction(step=step, spec=spec)
    for slot in spec.slots:
        arg = step.args[slot.name]
        prov = arg.prov
        if arg.kind == "handle":
            try:
                rec = store.get(arg.value)
            except UnknownHandle:
                raise BindError(
                    f"{slot.name} refers to {arg.value}, which is not on file"
                ) from None
            if slot.handle_kind and rec.kind != slot.handle_kind:
                raise BindError(f"{slot.name} expects a {slot.handle_kind} handle")
            ba.resolved[slot.name] = rec
            prov = rec.prov
            parent = rec.data.get("payee")
            if parent and store.has(parent):
                prec = store.get(parent)
                if prec.stained:
                    # A stained payee stains its accounts: an attacker who plants
                    # a note in one message cannot spend it in the next.
                    prov = prov.stained_by(prec.prov.refs)
            if rec.kind == "payee":
                ba.payee_handle = rec.handle
            if rec.kind == "account":
                ba.payee_handle = ba.payee_handle or rec.data.get("payee")
        if arg.kind == "money" and slot.enveloped and slot.name == "amount":
            ba.amount = float(arg.value)
        ba.effective[slot.name] = prov
    if spec.name == "pay_bill":
        if ba.resolved["account"].data.get("payee") != ba.resolved["payee"].handle:
            raise BindError("The destination account does not belong to the selected payee")
    return ba


class Gate:
    def __init__(self, mandates, ledger, baseline, escalations, max_privileged_per_hour: int = 12):
        self.mandates = mandates
        self.ledger = ledger
        self.baseline = baseline
        self.escalations = escalations
        self.max_privileged_per_hour = max_privileged_per_hour

    def evaluate(self, ba: BoundAction) -> tuple:
        reasons: list = []
        add = reasons.append
        spec = ba.spec

        # L0 -- system state. Fail closed, never open.
        if self.escalations.locked_down:
            add(Reason("GATE-LOCKDOWN", "L0", Decision.BLOCK,
                       "Airlock is paused: too many decisions needed at once, which is "
                       "itself a sign something is wrong."))

        # L1 -- mandate coverage. Autonomy exists only where the user granted it.
        mandate = self.mandates.for_action(spec.name, ba.payee_handle)
        if mandate is None:
            add(Reason("GATE-NO-MANDATE", "L1", Decision.ESCALATE,
                       f"You haven't pre-approved {spec.name.replace('_', ' ')}"
                       + (f" for this payee." if ba.payee_handle else ".")))

        # L2 -- the invariant. Effect-determining arguments must be trusted,
        # or must fall inside a bound the user wrote down in advance.
        for slot in spec.slots:
            prov: Provenance = ba.effective[slot.name]
            if prov.trusted:
                continue
            docs = sorted(r for r in prov.refs if r.startswith("email:"))
            where = ", ".join(docs) or "content from outside"
            if slot.destination:
                rec = ba.resolved.get(slot.name)
                if rec is not None:
                    add(Reason("GATE-STAINED-DEST", "L2", Decision.ESCALATE,
                               f"The destination on file was last changed based on "
                               f"{where}, not by you."))
                else:
                    add(Reason("GATE-UNTRUSTED-DEST", "L2", Decision.ESCALATE,
                               f"Where this goes was taken from {where}. Airlock never "
                               f"sets a destination from content it didn't get from you."))
            elif slot.enveloped:
                env = (mandate.envelopes.get(slot.name) if mandate else None)
                value = float(ba.step.args[slot.name].value)
                if env is None:
                    add(Reason("GATE-UNBOUNDED", "L2", Decision.ESCALATE,
                               f"{slot.name} came from {where} and you haven't set a "
                               f"limit for it."))
                else:
                    hist = self.baseline.store.history(ba.payee_handle) if ba.payee_handle else []
                    ok, why = env.admits(value, hist)
                    if not ok:
                        add(Reason("GATE-ENVELOPE", "L2", Decision.ESCALATE,
                                   f"{why}, so this one needs you."))
            elif spec.external or spec.irreversible:
                if ba.step.args[slot.name].kind == "handle":
                    add(Reason("GATE-STAINED-REF", "L2", Decision.ESCALATE,
                               f"The {slot.name} record on file was last changed based "
                               f"on {where}, not by you."))
                else:
                    add(Reason("GATE-UNTRUSTED-CONTENT", "L2", Decision.ESCALATE,
                               f"{slot.name} is text taken from {where} and this action "
                               f"leaves the house."))

        # L3 -- irreversibility.
        if spec.irreversible and (mandate is None or not mandate.allow_irreversible):
            add(Reason("GATE-IRREVERSIBLE", "L3", Decision.ESCALATE,
                       "This can't be undone once it's done."))

        # L4 -- the trifecta, at session scope. Intentionally redundant with L2:
        # if L2 is ever breached, this must not fall with it.
        if (self.ledger.tainted and self.ledger.sensitive_read
                and spec.external and self._unbounded(ba, mandate)):
            add(Reason("GATE-TRIFECTA", "L4", Decision.ESCALATE,
                       "This session has your private data, content from outside, and "
                       "a way to send things out, and this action isn't fully "
                       "determined by your own records."))

        # L5 -- behavioural baseline. Advisory only: it can raise a hand, never
        # lower one.
        for note in self.baseline.check(spec.name, ba.payee_handle, ba.amount):
            add(Reason("GATE-ANOMALY", "L5", Decision.ESCALATE, note.capitalize() + "."))

        # L5h -- hidden content. If the untrusted message carried something a
        # human reading it would not see (invisible characters, white/zero-size
        # HTML text, an HTML comment, an encoded blob, a risky attachment or a
        # hidden rules/config file), a money-moving action off the back of it
        # goes to the human. Advisory like L5: this can only raise, never clear,
        # and a clean scan is never treated as approval.
        if ba.privileged and self.ledger.current_flags:
            shown = "; ".join(self.ledger.current_flags[:3])
            add(Reason("GATE-HIDDEN", "L5h", Decision.ESCALATE,
                       f"This message hid something a normal reader wouldn't see "
                       f"({shown}). Airlock won't act on it on its own."))

        # L6 -- volume. A burst of privileged actions is itself suspicious.
        if ba.privileged and self.ledger.recent_privileged() >= self.max_privileged_per_hour:
            add(Reason("GATE-RATE", "L6", Decision.ESCALATE,
                       "Unusually many money-moving actions in a short window."))

        decision = Decision.ALLOW
        for r in reasons:
            if _RANK[r.decision] > _RANK[decision]:
                decision = r.decision
        return decision, reasons

    def _unbounded(self, ba: BoundAction, mandate) -> bool:
        """Is any effect-determining argument untrusted and outside a user bound?

        Deliberately a second, independent implementation of the same policy L2
        enforces. Two code paths agreeing is the point: a bug in one does not
        silently open the other.
        """
        for slot in ba.spec.slots:
            if ba.effective[slot.name].trusted:
                continue
            if slot.destination:
                return True
            env = mandate.envelopes.get(slot.name) if mandate else None
            if env is None:
                return True
            arg = ba.step.args[slot.name]
            if arg.kind != "money":
                return True
            hist = self.baseline.store.history(ba.payee_handle) if ba.payee_handle else []
            ok, _ = env.admits(float(arg.value), hist)
            if not ok:
                return True
        return False
