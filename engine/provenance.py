"""Provenance: every value in the system carries where it came from.

The whole architecture rests on one distinction that LLMs cannot make reliably
on their own: did this value originate from the user / a system of record, or
did it arrive inside content an attacker could have written?
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class Origin(str, Enum):
    USER = "USER"                      # typed by the human, or a signed mandate
    SYSTEM_OF_RECORD = "SYSTEM_OF_RECORD"  # bank / payee ledger the user configured
    AGENT = "AGENT"                    # derived purely from trusted inputs
    UNTRUSTED = "UNTRUSTED"            # email, web page, PDF, third-party tool output


TRUSTED_ORIGINS = frozenset({Origin.USER, Origin.SYSTEM_OF_RECORD, Origin.AGENT})


@dataclass(frozen=True)
class Provenance:
    origin: Origin
    refs: frozenset = frozenset()

    @property
    def trusted(self) -> bool:
        return self.origin in TRUSTED_ORIGINS

    def merge(self, other: "Provenance") -> "Provenance":
        """Combining values combines their taint. Untrusted is absorbing."""
        if self.origin is Origin.UNTRUSTED or other.origin is Origin.UNTRUSTED:
            origin = Origin.UNTRUSTED
        else:
            origin = Origin.AGENT
        return Provenance(origin, self.refs | other.refs)

    def stained_by(self, refs: Iterable[str]) -> "Provenance":
        """Permanently mark this value as untrusted-derived.

        Used when a record in the trusted store is written while the session is
        carrying untrusted content. The stain outlives the session -- this is
        what defeats attacks split across several messages.
        """
        return Provenance(Origin.UNTRUSTED, self.refs | frozenset(refs))

    def describe(self) -> str:
        if not self.refs:
            return self.origin.value.lower()
        return f"{self.origin.value.lower()} ({', '.join(sorted(self.refs))})"


def by_user(ref: str = "user") -> Provenance:
    return Provenance(Origin.USER, frozenset({ref}))


def by_record(ref: str) -> Provenance:
    return Provenance(Origin.SYSTEM_OF_RECORD, frozenset({ref}))


def by_agent(ref: str = "agent") -> Provenance:
    return Provenance(Origin.AGENT, frozenset({ref}))


def untrusted(ref: str) -> Provenance:
    return Provenance(Origin.UNTRUSTED, frozenset({ref}))
