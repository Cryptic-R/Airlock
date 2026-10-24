"""Session ledger: what this session has touched, accumulated over time.

The single most useful thing here is that the trifecta is evaluated over the
*session*, not over one tool call. An attack that splits itself across two
innocent-looking calls still lights up the ledger.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import time


@dataclass
class SessionLedger:
    session_id: str
    untrusted_refs: set = field(default_factory=set)
    sensitive_read: bool = False
    privileged_actions: list = field(default_factory=list)
    started: float = field(default_factory=time.time)
    # Hidden-content findings for the message currently being processed. Set at
    # ingest, cleared before the next message. Advisory: the gate may use it to
    # raise an action to review, never to clear one.
    current_flags: list = field(default_factory=list)

    def ingest_untrusted(self, ref: str, flags: list | None = None) -> None:
        self.untrusted_refs.add(ref)
        self.current_flags = list(flags or [])

    def note_sensitive_read(self, ref: str) -> None:
        self.sensitive_read = True

    def note_privileged(self, action: str) -> None:
        self.privileged_actions.append((action, time.time()))

    @property
    def tainted(self) -> bool:
        return bool(self.untrusted_refs)

    def recent_privileged(self, window: float = 3600.0) -> int:
        now = time.time()
        return sum(1 for _, t in self.privileged_actions if now - t <= window)
