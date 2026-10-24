"""Tool registry.

Every tool declares its capabilities up front, and every argument slot declares
what kind of value may occupy it. The gate reads these declarations; it never
reads the planner's description of what it is doing.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Slot:
    name: str
    kinds: tuple           # which ArgValue kinds may fill this slot
    handle_kind: str | None = None
    destination: bool = False   # decides *where* value or data goes
    enveloped: bool = False     # an untrusted value here must fit a user-authored envelope


@dataclass(frozen=True)
class ToolSpec:
    name: str
    summary: str
    slots: tuple
    sensitive: bool = False      # reads or uses private data
    external: bool = False       # moves value or data outside the user's boundary
    irreversible: bool = False
    stains_handle_slot: str | None = None  # writing to the store via this slot

    def slot(self, name: str) -> Slot | None:
        for s in self.slots:
            if s.name == name:
                return s
        return None


REGISTRY: dict[str, ToolSpec] = {}


def register(spec: ToolSpec) -> ToolSpec:
    REGISTRY[spec.name] = spec
    return spec


register(ToolSpec(
    name="pay_bill",
    summary="Pay a bill from the user's account",
    slots=(
        Slot("payee", kinds=("handle",), handle_kind="payee"),
        Slot("account", kinds=("handle",), handle_kind="account", destination=True),
        Slot("amount", kinds=("money",), enveloped=True),
    ),
    sensitive=True, external=True, irreversible=True,
))

register(ToolSpec(
    name="add_payee_account",
    summary="Add a new destination account for a payee",
    slots=(
        Slot("payee", kinds=("handle",), handle_kind="payee"),
        Slot("account_number", kinds=("quote", "text"), destination=True),
    ),
    sensitive=True, external=False, irreversible=True,
    stains_handle_slot="payee",
))

register(ToolSpec(
    name="update_payee_note",
    summary="Store a note against a payee",
    slots=(
        Slot("payee", kinds=("handle",), handle_kind="payee"),
        Slot("note", kinds=("quote", "text")),
    ),
    stains_handle_slot="payee",
))

register(ToolSpec(
    name="schedule_reminder",
    summary="Put a dated reminder on the user's calendar",
    slots=(
        Slot("topic", kinds=("text", "quote")),
        Slot("days_ahead", kinds=("money",), enveloped=True),
    ),
))

register(ToolSpec(
    name="draft_return_request",
    summary="Write a return request and leave it in drafts, unsent",
    slots=(
        Slot("order", kinds=("quote", "text")),
    ),
    sensitive=True,
))

register(ToolSpec(
    name="send_email",
    summary="Send an email on the user's behalf",
    slots=(
        Slot("to", kinds=("quote", "text"), destination=True),
        Slot("body", kinds=("quote", "text")),
    ),
    sensitive=True, external=True, irreversible=True,
))

register(ToolSpec(
    name="notify_user",
    summary="Tell the user something",
    slots=(
        Slot("message", kinds=("text", "quote")),
    ),
))
