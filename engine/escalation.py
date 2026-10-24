"""The escalation queue -- and its own defence.

The queue is a target, not just a safety net: flood a human with borderline
approvals and they start clicking yes. So the queue deduplicates, rate limits,
and when it overflows it stops the agent rather than the questions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import time
from uuid import uuid4


@dataclass
class Escalation:
    signature: str
    summary: str
    reasons: list
    action: object = None     # the BoundAction this was raised for
    count: int = 1
    first_seen: float = field(default_factory=time.time)
    status: str = "open"


class EscalationQueue:
    def __init__(self, max_per_hour: int = 8, capacity: int = 12):
        self.max_per_hour = max_per_hour
        self.capacity = capacity
        self.items: dict = {}
        self.timeline: list = []
        self.locked_down = False
        self.lockdown_reason = ""
        self._groups: dict[str, str] = {}

    def raise_for(self, action_desc: str, reasons: list, action=None) -> Escalation:
        group = "|".join(sorted(r.code for r in reasons)) + "::" + action_desc.split("(")[0]
        now = time.time()
        self.timeline.append(now)
        item = self.items.get(self._groups.get(group, ""))
        sig = uuid4().hex
        if item and item.status == "open":
            # Near-identical requests collapse into one so a flood cannot become
            # a wall of clicks. Approving carries out only the latest of them.
            item.count += 1
            # Invalidate an old card when the action it displayed changes.
            self.items.pop(item.signature)
            item.signature = sig
            item.summary = action_desc
            item.action = action
            item.reasons = list(reasons)
        else:
            item = Escalation(sig, action_desc, list(reasons), action=action)
        self.items[sig] = item
        self._groups[group] = sig
        self._check_pressure()
        return item

    def _check_pressure(self) -> None:
        now = time.time()
        recent = [t for t in self.timeline if now - t <= 3600]
        distinct_open = sum(1 for i in self.items.values() if i.status == "open")
        if len(recent) > self.max_per_hour or distinct_open > self.capacity:
            self.locked_down = True
            self.lockdown_reason = (
                f"{len(recent)} approvals requested in an hour. Airlock stopped acting "
                f"and is waiting for you, rather than asking you to keep clicking."
            )

    def open_items(self) -> list:
        return [i for i in self.items.values() if i.status == "open"]

    def resolve(self, signature: str, approved: bool) -> None:
        item = self.items.get(signature)
        if not item:
            return
        item.status = "approved" if approved else "declined"
        if not self.open_items():
            # The human has caught up, so the agent may act again.
            self.locked_down = False
            self.lockdown_reason = ""
            self.timeline.clear()
