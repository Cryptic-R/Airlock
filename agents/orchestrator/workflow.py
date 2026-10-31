"""Orchestration: Reader agent (untrusted input) -> Airlock engine (plan+gate+act)
-> Bank agent (settle approved effects). Each hop has a local fallback so a missing
helper never leaves the user without a reply."""

import asyncio
import json
from uuid import uuid4

from uagents import Context

from common import cards, service
from common.config import BANK_ADDRESS, HELPER_TIMEOUT_S, READER_ADDRESS
from common.models import ExecRequest, ExecResult, ReadRequest, ReadResult
from engine.seed import INBOX
from common.parse import parse_email


async def _read(ctx: Context, mode: str, raw_text: str = "") -> list[dict]:
    job = uuid4().hex[:8]
    try:
        reply, status = await ctx.send_and_receive(
            READER_ADDRESS, ReadRequest(job_id=job, mode=mode, raw_text=raw_text),
            response_type=ReadResult, timeout=int(HELPER_TIMEOUT_S))
        if isinstance(reply, ReadResult) and reply.ok:
            return json.loads(reply.messages_json)
    except Exception as exc:
        ctx.logger.warning(f"reader unavailable ({exc}); reading locally")
    return [dict(m) for m in INBOX] if mode == "inbox" else [parse_email(raw_text)]


async def _settle(ctx: Context, action: str, hint: str, amount: float = 0.0, payee: str = "") -> str:
    job = uuid4().hex[:8]
    try:
        reply, status = await ctx.send_and_receive(
            BANK_ADDRESS, ExecRequest(job_id=job, action=action, receipt_hint=hint,
                                      amount=amount, payee_name=payee),
            response_type=ExecResult, timeout=int(HELPER_TIMEOUT_S))
        if isinstance(reply, ExecResult) and reply.ok:
            return reply.receipt
    except Exception as exc:
        ctx.logger.warning(f"bank unavailable ({exc}); settling locally")
    return "Bank confirmation unavailable. " + (hint or "No settlement confirmed.")


async def run_inbox(ctx: Context, user: str) -> None:
    msgs = await _read(ctx, "inbox")
    await _run_and_reply(ctx, user, msgs, intro=f"Reading {len(msgs)} messages from your inbox...")


async def run_paste(ctx: Context, user: str, raw_text: str) -> None:
    msgs = await _read(ctx, "parse", raw_text)
    await _run_and_reply(ctx, user, msgs, intro="Reading that message...")


async def _run_and_reply(ctx: Context, user: str, msgs: list[dict], intro: str) -> None:
    await ctx.send(user, cards.text_message("🛰️ " + intro))
    summary = await asyncio.to_thread(service.run_messages, user, msgs)
    # Let the Bank agent confirm each autonomously-paid bill (real agent hop).
    for h in summary["handled"]:
        if h["action"].startswith("pay_bill"):
            await _settle(ctx, "pay_bill", h["receipt"])
    await ctx.send(user, cards.card_message("custom", cards.summary_card(summary),
                                            narration="Here's what Airlock did."))
    # Keep decisions in the summary card; separate cards may be hidden by ASI:One.
    if not summary["decisions"]:
        await ctx.send(user, cards.text_message("Nothing needs you. All done."))
