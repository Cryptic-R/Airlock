"""ASI:One Interactive Card builders for Airlock (card_protocol_version 1).

Payload shapes follow uagents_core.contrib.protocols.chat.cards; tests validate them.
"""

import json
from datetime import datetime, timezone
from uuid import uuid4

from uagents_core.contrib.protocols.chat import (
    ChatMessage,
    EndSessionContent,
    MetadataContent,
    TextContent,
)


def text_message(text: str, end_session: bool = False) -> ChatMessage:
    content = [TextContent(type="text", text=text)]
    if end_session:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(timestamp=datetime.now(timezone.utc), msg_id=uuid4(), content=content)


def card_message(kind: str, payload: dict, narration: str = "", terminal: bool = False, width: int = 600) -> ChatMessage:
    meta = {
        "card_protocol_version": "1",
        "requires_card_interaction": "true",
        "card_kind": kind,
        "card_payload": json.dumps(payload),
        "card_id": str(uuid4()),
        "preferred_drawer_width_px": str(width),
    }
    if terminal:
        meta["is_terminal"] = "true"
    content = [TextContent(type="text", text=narration)] if narration else []
    content.append(MetadataContent(type="metadata", metadata=meta))
    return ChatMessage(timestamp=datetime.now(timezone.utc), msg_id=uuid4(), content=content)


def _badge(label, variant=None):
    b = {"type": "badge", "label": label}
    if variant:
        b["variant"] = variant
    return b


def welcome_card() -> dict:
    return {"root": {
        "type": "section",
        "title": "Airlock",
        "subtitle": "Pays the recurring bills on its own. Stops the moment an email tries to change what it does.",
        "children": [
            {"type": "text", "style": "muted",
             "value": "Demo: runs a sample inbox and records simulated bill payments. No real bank, email, or calendar is connected."},
            {"type": "group", "direction": "row", "gap": 8, "children": [
                {"type": "button", "label": "Run my inbox", "primary": True,
                 "action": {"selection": {"action": "run_inbox"}}},
                {"type": "button", "label": "What may it do on its own?",
                 "action": {"selection": {"action": "show_mandates"}}},
            ]},
            {"type": "text", "style": "muted",
             "value": "Or paste an email (subject + body) and I'll decide what to do with it."},
        ],
    }}


def mandates_card(rows: list[dict]) -> dict:
    children = [{"type": "text", "style": "muted",
                 "value": "Autonomy exists only where you authored it. Everything else needs you."}]
    for r in rows:
        children.append({"type": "section", "title": r["name"], "children": [
            {"type": "text", "value": f"May: {r['actions']}", "style": "body"},
            {"type": "text", "value": f"Limits: {r['bounds']}", "style": "muted"},
        ]})
    children.append({"type": "button", "label": "Run my inbox", "primary": True,
                     "action": {"selection": {"action": "run_inbox"}}})
    return {"root": {"type": "section", "title": "Your standing mandates", "children": children}}


def summary_card(s: dict) -> dict:
    badges = [
        _badge(f"{s['paid_count']} bill(s) paid", "success"),
        _badge(f"{len(s['decisions'])} need you", "warning" if s["decisions"] else "success"),
    ]
    if s.get("failed"):
        badges.append(_badge(f"{len(s['failed'])} payment failed", "danger"))
    if s["captured_any"]:
        badges.append(_badge("planner hit by injection — held anyway", "info"))
    children = [{"type": "group", "direction": "row", "gap": 8, "children": badges}]

    if s.get("already_paid"):
        children.append({"type": "text", "style": "muted",
                         "value": f"{len(s['already_paid'])} previously paid bill(s) skipped; no duplicate payment."})
    elif s.get("skipped"):
        children.append({"type": "text", "style": "muted",
                         "value": f"{len(s['skipped'])} already processed message(s) skipped; no repeated actions."})
    if s.get("failed"):
        fail_items = []
        for f in s["failed"]:
            fail_items.append({"children": [
                {"type": "text", "value": f"❌ Payment Failed (ID: {f.get('id', 'unknown')})", "style": "body"},
                {"type": "text", "value": f.get("reason", "Payment failed"), "style": "muted"},
            ]})
        children += [{"type": "divider"},
                     {"type": "heading", "level": 3, "value": "Payment Failures Flagged"},
                     {"type": "list", "items": fail_items}]
    if s["blocked"]:
        children.append({"type": "text", "style": "body",
                         "value": "Blocked: " + "; ".join(r['subject'] + ": " + ", ".join(r['reasons']) for r in s['blocked'])})
    if s["handled"]:
        items = []
        for h in s["handled"]:
            detail = h["receipt"] or h["action"]
            items.append({"children": [
                {"type": "text", "value": f"✅ {h['subject']}", "style": "body"},
                {"type": "text", "value": detail, "style": "muted"},
            ]})
        children += [{"type": "divider"},
                     {"type": "heading", "level": 3, "value": "Handled on its own"},
                     {"type": "list", "items": items}]

    if s["decisions"]:
        children += [{"type": "divider"},
                     {"type": "heading", "level": 3, "value": "Waiting for you"},
                     {"type": "text", "style": "muted",
                      "value": "I've opened a card for each. Approve or decline below."}]

    if s["locked_down"]:
        children += [{"type": "divider"},
                     {"type": "text", "style": "emphasis", "value": "⏸ " + s["lockdown_reason"]}]

    children += [{"type": "divider"},
                 {"type": "text", "style": "muted",
                  "value": f"Audit chain: {s['audit_len']} entries, intact = {s['audit_ok']}."}]
    return {"root": {"type": "section", "title": "Airlock ran your sample inbox", "subtitle": "Payments and household actions are simulated in a demo ledger.", "children": children}}



def review_card(decision: dict) -> dict:
    """A review card for one escalation: approve or decline."""
    rows = [{"label": "Action", "value": decision["summary"]}]
    for i, why in enumerate(decision["reasons"][:4], 1):
        rows.append({"label": f"Why #{i}", "value": why})
    if decision["count"] > 1:
        rows.append({"label": "Note", "value": f"{decision['count']} near-identical requests collapsed into this one."})
    approve_label = "Approve & pay" if decision["is_payment"] else "Approve"
    return {
        "title": "Airlock needs your decision",
        "summary_rows": rows,
        "approve_cta": {"label": approve_label, "selection": {"action": "approve", "sig": decision["signature"]}, "primary": True},
        "reject_cta": {"label": "Decline", "selection": {"action": "decline", "sig": decision["signature"]}},
    }


def error_card(message: str, retry_selection: dict | None = None) -> dict:
    children = [{"type": "text", "value": message, "style": "body"}]
    if retry_selection:
        children.append({"type": "button", "label": "Try again", "primary": True,
                         "action": {"selection": retry_selection}})
    return {"root": {"type": "section", "title": "Something went wrong", "children": children}}
