"""The Planner/Actor interface.

This module is the seam that isolation-breach attacks aim at, so it is
deliberately the most boring, most strict code in the project: a closed schema
with no free-text channel to the Actor. The planner's prose reasoning exists,
but it goes to the audit log and to the human. It never crosses this boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import math

from .provenance import Provenance, by_agent, untrusted
from .tools import REGISTRY

ARG_KINDS = {"handle", "money", "text", "quote"}


class PlanRejected(Exception):
    """Raised when planner output does not match the schema. Always fail closed."""


@dataclass(frozen=True)
class Arg:
    kind: str
    value: Any
    prov: Provenance

    def render(self) -> str:
        if self.kind == "money":
            return f"{self.value:,.2f}"
        return str(self.value)


@dataclass(frozen=True)
class Step:
    action: str
    args: dict          # slot name -> Arg


@dataclass(frozen=True)
class Plan:
    steps: tuple
    # narrative is carried for humans and the audit log only; parse_plan keeps it
    # out of Step entirely so it cannot be handed to the Actor by accident.


def _reject(msg: str):
    raise PlanRejected(msg)


def parse_plan(raw: Any, source_ref: str) -> Plan:
    """Parse untrusted planner output into a typed plan, or refuse.

    `source_ref` is the untrusted document the planner was reading. Any literal
    text the planner passes through is attributed to it automatically -- the
    planner does not get to declare its own output trusted.
    """
    if not isinstance(raw, dict):
        _reject("plan must be an object")
    extra = set(raw) - {"steps"}
    if extra:
        _reject(f"unexpected top-level field(s): {sorted(extra)}")
    steps_raw = raw.get("steps")
    if not isinstance(steps_raw, list) or not steps_raw:
        _reject("plan must contain a non-empty 'steps' list")
    if len(steps_raw) > 8:
        _reject("plan exceeds the 8-step limit")

    steps = []
    for i, s in enumerate(steps_raw):
        if not isinstance(s, dict):
            _reject(f"step {i} is not an object")
        extra = set(s) - {"action", "args"}
        if extra:
            _reject(f"step {i} has unexpected field(s): {sorted(extra)}")
        action = s.get("action")
        if not isinstance(action, str):
            _reject(f"step {i} action must be a string")
        spec = REGISTRY.get(action)
        if spec is None:
            _reject(f"step {i} names an unknown action: {action!r}")
        args_raw = s.get("args")
        if not isinstance(args_raw, dict):
            _reject(f"step {i} args must be an object")

        declared = {sl.name for sl in spec.slots}
        if set(args_raw) != declared:
            _reject(
                f"step {i} ({action}) args must be exactly {sorted(declared)}, "
                f"got {sorted(args_raw)}"
            )

        args = {}
        for slot in spec.slots:
            a = args_raw[slot.name]
            if not isinstance(a, dict):
                _reject(f"step {i} arg {slot.name} must be an object")
            kind = a.get("kind")
            if not isinstance(kind, str) or kind not in ARG_KINDS:
                _reject(f"step {i} arg {slot.name} has unknown kind {kind!r}")
            if kind not in slot.kinds:
                _reject(
                    f"step {i} arg {slot.name} may not be a {kind}; "
                    f"this slot accepts {list(slot.kinds)}"
                )
            value = a.get("value")
            if "source_ref" in a and not isinstance(a["source_ref"], str):
                _reject(f"step {i} arg {slot.name} source_ref must be a string")
            if kind == "handle":
                if not isinstance(value, str) or ":" not in value:
                    _reject(f"step {i} arg {slot.name} is not a handle")
                prov = by_agent("plan")
            elif kind == "money":
                if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
                    _reject(f"step {i} arg {slot.name} is not a non-negative number")
                value = float(value)
                if not math.isfinite(value):
                    _reject(f"step {i} arg {slot.name} must be finite")
                # numbers lifted out of the document are untrusted, always
                prov = untrusted(a.get("source_ref") or source_ref)
            elif kind == "quote":
                if not isinstance(value, str):
                    _reject(f"step {i} arg {slot.name} quote must be a string")
                ref = a.get("source_ref") or source_ref
                if not isinstance(ref, str):
                    _reject(f"step {i} arg {slot.name} quote needs a source_ref")
                prov = untrusted(ref)
            else:  # text -- planner-authored prose, still untrusted-derived
                if not isinstance(value, str):
                    _reject(f"step {i} arg {slot.name} text must be a string")
                prov = untrusted(source_ref)
            allowed_keys = {"kind", "value", "source_ref"}
            if set(a) - allowed_keys:
                _reject(f"step {i} arg {slot.name} has unexpected field(s)")
            args[slot.name] = Arg(kind, value, prov)
        steps.append(Step(action, args))
    return Plan(tuple(steps))
