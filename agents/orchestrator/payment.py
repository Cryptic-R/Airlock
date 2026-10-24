"""Agent Payment Protocol (seller): settling an approved bill in FET.

When the user approves an escalated payment, the amount they authorised is
settled on-chain (testnet by default). Non-payment approvals, and all approvals
when payments are disabled, execute directly without a payment step.
"""

import asyncio

from uagents import Context, Protocol
from uagents_core.contrib.protocols.payment import (
    CancelPayment,
    CommitPayment,
    CompletePayment,
    Funds,
    RejectPayment,
    RequestPayment,
    payment_protocol_spec,
)

from common import cards, service
from common.config import BILL_TO_FET, FET_USE_TESTNET

payment_proto = Protocol(spec=payment_protocol_spec, role="seller")

_wallet = None


def set_agent_wallet(wallet) -> None:
    global _wallet
    _wallet = wallet


def _pending_key(user: str) -> str:
    return f"pending_pay:{user}"


async def request_bill_payment(ctx: Context, user: str, decision: dict) -> None:
    """Ask the user to settle an approved bill in FET."""
    amount_fet = max(0.000001, round(decision["amount"] * BILL_TO_FET, 6))
    recipient = str(_wallet.address()) if _wallet else str(ctx.agent.address)
    ctx.storage.set(_pending_key(user), {
        "sig": decision["signature"], "bill_amount": decision["amount"],
        "payee": decision["payee_name"], "amount_fet": f"{amount_fet}",
        "msg_id": decision.get("message_id"),
    })
    await ctx.send(user, RequestPayment(
        accepted_funds=[Funds(currency="FET", amount=f"{amount_fet}", payment_method="fet_direct")],
        recipient=recipient,
        deadline_seconds=300,
        reference=decision["signature"][:40],
        description=f"Airlock: settle approved bill of {decision['amount']:,.2f} to {decision['payee_name']} ({amount_fet} FET)",
        metadata={
            "agent": "airlock", "service": "bill_settlement",
            "fet_network": "stable-testnet" if FET_USE_TESTNET else "mainnet",
            "mainnet": "false" if FET_USE_TESTNET else "true",
            "provider_agent_wallet": recipient,
            "content": f"Pay {amount_fet} FET to settle the approved bill.",
        },
    ))


def _verify_fet_payment(tx_hash: str, amount_fet: str, buyer: str | None) -> bool:
    from cosmpy.aerial.client import LedgerClient, NetworkConfig
    cfg = NetworkConfig.fetchai_stable_testnet() if FET_USE_TESTNET else NetworkConfig.fetchai_mainnet()
    denom = "atestfet" if FET_USE_TESTNET else "afet"
    expected = int(float(amount_fet) * 10**18)
    me = str(_wallet.address()) if _wallet else ""
    tx = LedgerClient(cfg).query_tx(tx_hash)
    if not tx.is_successful():
        return False
    for etype, attrs in tx.events.items():
        if etype != "transfer" or attrs.get("recipient") != me:
            continue
        if buyer and attrs.get("sender") not in (None, buyer):
            continue
        amt = attrs.get("amount", "")
        if amt.endswith(denom) and int(amt[: -len(denom)] or 0) >= expected:
            return True
    return False


@payment_proto.on_message(CommitPayment)
async def on_commit(ctx: Context, sender: str, msg: CommitPayment):
    pending = ctx.storage.get(_pending_key(sender)) or {}
    used_key = f"used_payment:{msg.transaction_id}"
    if (not pending or ctx.storage.get(used_key)
            or not service.decision_by_signature(sender, pending.get("sig", ""))):
        await ctx.send(sender, CancelPayment(transaction_id=msg.transaction_id,
                                             reason="No current approval or transaction already used"))
        return
    ok = False
    if msg.funds.currency == "FET" and msg.funds.payment_method == "fet_direct":
        buyer = None
        if isinstance(msg.metadata, dict):
            buyer = msg.metadata.get("buyer_fet_wallet") or msg.metadata.get("buyer_fet_address")
        for attempt in range(3):
            try:
                ok = await asyncio.to_thread(_verify_fet_payment, msg.transaction_id,
                                             pending.get("amount_fet", str(msg.funds.amount)), buyer)
            except Exception as exc:
                ctx.logger.warning(f"verify attempt {attempt + 1} failed: {exc}")
            if ok:
                break
            await asyncio.sleep(4)
    if not ok:
        await ctx.send(sender, CancelPayment(transaction_id=msg.transaction_id, reason="Payment could not be verified on-chain"))
        msg_id = pending.get("msg_id") or pending.get("sig", "")
        if msg_id:
            await asyncio.to_thread(service.flag_payment_failed, sender, msg_id, "On-chain FET payment verification failed")
        await ctx.send(sender, cards.text_message("⚠️ I couldn't verify that payment on-chain, so the bill was flagged with a failed payment. You can try the approval again."))
        return
    ctx.storage.set(used_key, {"user": sender, "sig": pending["sig"]})
    await _finalise_approval(ctx, sender, pending.get("sig", ""))
    await ctx.send(sender, CompletePayment(transaction_id=msg.transaction_id))


async def _finalise_approval(ctx: Context, user: str, signature: str) -> None:
    """Execute the held action in the engine and confirm via the Bank agent."""
    from agents.orchestrator.workflow import _settle
    try:
        receipt = await asyncio.to_thread(service.approve, user, signature)
    except Exception as exc:
        await ctx.send(user, cards.text_message(f"Couldn't finalise that approval ({exc})."))
        return
    bank = await _settle(ctx, "pay_bill", receipt)
    ctx.storage.remove(_pending_key(user))
    await ctx.send(user, cards.text_message(f"✅ Demo approval recorded. {bank}"))


@payment_proto.on_message(RejectPayment)
async def on_reject(ctx: Context, sender: str, msg: RejectPayment):
    pending = ctx.storage.get(_pending_key(sender)) or {}
    ctx.storage.remove(_pending_key(sender))
    msg_id = pending.get("msg_id") or pending.get("sig", "")
    if msg_id:
        await asyncio.to_thread(service.flag_payment_failed, sender, msg_id, "Payment rejected by user")
    await ctx.send(sender, cards.text_message("⚠️ Payment was declined and flagged as failed. It's still waiting if you change your mind."))

