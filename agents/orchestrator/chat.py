"""Agent Chat Protocol handler: the Airlock conversation in ASI:One.

Flow: welcome -> run inbox (or paste an email) -> summary + a review card per
escalation -> Approve (settles in FET) / Decline.
"""

import asyncio
import json
import re
from datetime import datetime, timezone

from uagents import Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    MetadataContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)
from uagents_core.contrib.protocols.chat.cards import extract_card_response

import common.config as config
from agents.orchestrator.payment import request_bill_payment, _finalise_approval
from agents.orchestrator.workflow import _settle, run_inbox, run_paste
from common import cards, service

chat_proto = Protocol(spec=chat_protocol_spec)
ACTIONS = ("run_inbox", "show_mandates", "approve", "decline", "reset")

WELCOME = (
    "🔒 **I'm Airlock.** I pay your recurring household bills on my own, and I stop the "
    "moment an email tries to change *what* a payment does — a new account number, a surprise "
    "amount, a request to forward your statements. Tap **Run my inbox** to see it, or paste an email."
)


def _strip(text: str) -> str:
    return re.sub(r"^@\S+\s*", "", (text or "").strip())


def parse_selection(text: str) -> dict:
    text = _strip(text)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    for cand in (text, m.group() if m else None):
        if not cand:
            continue
        try:
            d = json.loads(cand)
            if isinstance(d, dict):
                return d
        except (json.JSONDecodeError, TypeError):
            pass
    sel: dict = {}
    if re.search(r"\b(run|inbox|check)\b", text, re.I):
        sel["action"] = "run_inbox"
    elif re.search(r"\b(mandate|rules|allowed)\b", text, re.I):
        sel["action"] = "show_mandates"
    return sel


def _looks_like_email(text: str) -> bool:
    t = text.lower()
    return (len(text) > 60 or "\n" in text) and any(
        k in t for k in ("subject:", "from:", "due", "invoice", "bill", "amount", "$", "£", "€", "account", "payment"))


async def _approve(ctx: Context, user: str, signature: str) -> None:
    decision = service.decision_by_signature(user, signature)
    if not decision:
        await ctx.send(user, cards.text_message("That decision isn't open any more."))
        return
    if decision["is_payment"] and config.ENABLE_PAYMENTS:
        await request_bill_payment(ctx, user, decision)
        return
    # non-payment approval, or payments disabled: execute directly
    if decision["is_payment"]:
        await _finalise_approval(ctx, user, signature)
    else:
        try:
            receipt = await asyncio.to_thread(service.approve, user, signature)
        except Exception as exc:
            await ctx.send(user, cards.text_message(f"Couldn't apply that approval ({exc})."))
            return
        await ctx.send(user, cards.text_message(f"✅ Approved. {receipt}"))


async def handle_selection(ctx: Context, user: str, sel: dict) -> bool:
    action = sel.get("action")
    if action == "run_inbox":
        await run_inbox(ctx, user)
        return True
    if action == "show_mandates":
        await ctx.send(user, cards.card_message("custom", cards.mandates_card(service.mandates_summary(user))))
        return True
    if action == "approve" and sel.get("sig"):
        await _approve(ctx, user, sel["sig"])
        return True
    if action == "decline" and sel.get("sig"):
        await asyncio.to_thread(service.decline, user, sel["sig"])
        await ctx.send(user, cards.text_message("Declined. I won't act on that one."))
        return True
    if action == "reset":
        service.reset_lock(user)
        await ctx.send(user, cards.card_message("custom", cards.welcome_card(), narration="Fresh start."))
        return True
    return False


@chat_proto.on_message(ChatMessage)
async def on_chat(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(sender, ChatAcknowledgement(timestamp=datetime.now(timezone.utc), acknowledged_msg_id=msg.msg_id))
    text, card_sel, started = "", None, False
    for item in msg.content:
        if isinstance(item, StartSessionContent):
            started = True
        elif isinstance(item, TextContent):
            text += item.text
        elif isinstance(item, MetadataContent):
            resp = extract_card_response(item)
            if resp and resp.selection:
                card_sel = dict(resp.selection)
            elif resp and resp.cancelled:
                await ctx.send(sender, cards.text_message("Okay, cancelled."))
                return
    text = _strip(text)
    ctx.logger.info(f"{sender[:16]}...: {text[:100]!r} sel={card_sel}")

    try:
        if not card_sel and text and _looks_like_email(text):
            await run_paste(ctx, sender, text)
            return
        sel = card_sel or (parse_selection(text) if text else {})
        if sel.get("action") and await handle_selection(ctx, sender, sel):
            return
        if text and _looks_like_email(text):
            await run_paste(ctx, sender, text)
            return
        # greetings / help / empty / anything else -> welcome
        await ctx.send(sender, cards.card_message("custom", cards.welcome_card(),
                                                  narration=WELCOME if (started or not text) else ""))
    except Exception as exc:
        ctx.logger.exception("chat handler failed")
        await ctx.send(sender, cards.text_message(f"Sorry, something went wrong on my side ({type(exc).__name__}). Please try again."))


@chat_proto.on_message(ChatAcknowledgement)
async def on_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    pass
