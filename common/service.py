"""Per-user Airlock sessions and helpers that turn engine objects into
card-ready dicts for the ASI:One layer.

State is cached per user and persisted transactionally as versioned JSON in SQLite.
The effects remain simulated; external payment reconciliation is not implemented.
"""

from functools import wraps
from engine.persistence import transaction
from engine import Airlock, LLMPlanner
from engine.gate import Decision
from engine.seed import INBOX, build_mandates, build_store
from engine.store import Payment

from common import asi1

_sessions: dict[str, Airlock] = {}


def _planner():
    return LLMPlanner(lambda messages: asi1.chat(messages, temperature=0, max_tokens=700))


def _fresh(user):
    return Airlock(build_store(), build_mandates(), _planner(), session_id=user[-8:] or "s1")


def durable(fn):
    @wraps(fn)
    def wrapped(user, *args, **kwargs):
        with transaction(user, _sessions, _fresh):
            return fn(user, *args, **kwargs)
    return wrapped


def get_lock(user: str) -> Airlock:
    lock = _sessions.get(user)
    if lock is None:
        lock = Airlock(build_store(), build_mandates(), _planner(), session_id=user[-8:] or "s1")
        _sessions[user] = lock
    return lock


@durable
def reset_lock(user: str) -> Airlock:
    _sessions.pop(user, None)
    return get_lock(user)


def demo_inbox() -> list[dict]:
    return [dict(m) for m in INBOX]


@durable
def mandates_summary(user: str) -> list[dict]:
    lock = get_lock(user)
    rows = []
    for m in lock.mandates.mandates:
        actions = ", ".join(sorted(a.replace("_", " ") for a in m.actions))
        env = "; ".join(f"{k} ≤ {v.ceiling:,.0f}" for k, v in m.envelopes.items())
        rows.append({"name": m.name, "actions": actions, "bounds": env or "—"})
    return rows


DECISION_WORD = {"ALLOW": "handled", "ESCALATE": "needs you", "BLOCK": "refused"}


@durable
def run_messages(user: str, messages: list[dict]) -> dict:
    """Process messages through Airlock and return a card-ready summary."""
    lock = get_lock(user)
    handled, blocked, skipped, already_paid, failed = [], [], [], [], []
    for msg in messages:
        key = str(msg.get("id", ""))
        res = lock.process(msg)
        for o in res.outcomes:
            row = {"id": key, "subject": res.subject, "action": o.action,
                   "decision": o.decision, "receipt": o.receipt,
                   "reasons": [r for r in o.reasons]}
            if o.decision == "ALLOW":
                handled.append(row)
            elif o.decision == "BLOCK":
                blocked.append(row)
            elif o.decision == "SKIP":
                skipped.append(row)
                if "paid" in o.action.lower() or "paid" in str(o.receipt).lower():
                    already_paid.append(row)
    
    for f_id, f_data in getattr(lock, "failed_payments", {}).items():
        failed.append({
            "id": f_id,
            "reason": f_data.get("reason", "Payment failed"),
            "status": "PAYMENT_FAILED",
            "timestamp": f_data.get("timestamp", 0),
        })

    new_pay = lock.store.payments[lock.store.seeded:]
    return {
        "handled": handled,
        "skipped": skipped,
        "already_paid": already_paid,
        "blocked": blocked,
        "failed": failed,
        "decisions": open_decisions(user),
        "paid_count": len(new_pay),
        "paid_total": round(sum(p.amount for p in new_pay), 2),
        "reminders": len(lock.store.reminders),
        "drafts": len(lock.store.drafts),
        "locked_down": lock.escalations.locked_down,
        "lockdown_reason": lock.escalations.lockdown_reason,
        "audit_ok": lock.audit.verify(),
        "audit_len": len(lock.audit.entries),
        "captured_any": _captured_any(lock),
    }


def _captured_any(lock: Airlock) -> bool:
    return any(e.payload.get("captured") for e in lock.audit.entries if e.kind == "planner_output")


@durable
def open_decisions(user: str) -> list[dict]:
    """Escalations waiting for the human, as card-ready dicts."""
    lock = get_lock(user)
    out = []
    for item in lock.escalations.open_items():
        ba = item.action
        amount = getattr(ba, "amount", None) if ba is not None else None
        payee_name = ""
        if ba is not None and ba.payee_handle and lock.store.has(ba.payee_handle):
            payee_name = lock.store.get(ba.payee_handle).data.get("name", "")
        msg_id = lock._find_msg_id_for_action(ba) if ba is not None else None
        out.append({
            "signature": item.signature,
            "summary": item.summary,
            "count": item.count,
            "reasons": [r.text for r in item.reasons],
            "is_payment": ba is not None and ba.spec.name == "pay_bill" and amount is not None,
            "amount": float(amount) if amount is not None else 0.0,
            "payee_name": payee_name,
            "message_id": msg_id,
        })
    return out


def decision_by_signature(user: str, signature: str) -> dict | None:
    for d in open_decisions(user):
        if d["signature"] == signature:
            return d
    return None


@durable
def approve(user: str, signature: str) -> str:
    """Execute a held action because the human approved it. Returns a receipt."""
    return get_lock(user).approve(signature)


@durable
def decline(user: str, signature: str) -> None:
    get_lock(user).decline(signature)


@durable
def flag_payment_failed(user: str, message_id: str, reason: str, details: dict | None = None) -> None:
    """Flag an email message with a failed payment."""
    get_lock(user).flag_failed_payment(message_id, reason, details)


@durable
def get_message_status(user: str, message_id: str) -> dict:
    """Get the current processing/payment status of an email message."""
    return get_lock(user).get_message_status(message_id)

