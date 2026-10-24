"""Airlock runtime: reader -> planner -> schema -> gate -> actor.

The ordering is the product. Untrusted content enters on the left and reaches
the right only as a typed, bounded, provenance-tagged action that a piece of
deterministic code has agreed to.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
import re
import tempfile
import time

from .actor import Actor
from .audit import AuditLog
from .baseline import Baseline
from .downloads import Quarantine
from .escalation import EscalationQueue
from .gate import BindError, Decision, Gate, bind
from .ledger import SessionLedger
from .plan import PlanRejected, parse_plan
from .scan import scan_text


@dataclass
class Outcome:
    decision: str
    action: str
    reasons: list = field(default_factory=list)
    receipt: str = ""


@dataclass
class MessageResult:
    message_id: str
    subject: str
    planner_captured: bool
    narrative: str
    outcomes: list = field(default_factory=list)

    @property
    def headline(self) -> str:
        if any(o.decision == "BLOCK" for o in self.outcomes):
            return "BLOCK"
        if any(o.decision == "ESCALATE" for o in self.outcomes):
            return "ESCALATE"
        return "ALLOW"


class Airlock:
    def __init__(self, store, mandates, planner, *, session_id="s1"):
        self.processed = {}
        self.paid_messages = {}
        self.paid_invoices = set()
        self.message_statuses = {}
        self.failed_payments = {}
        self.store = store
        self.mandates = mandates
        self.planner = planner
        self.ledger = SessionLedger(session_id)
        self.baseline = Baseline(store)
        self.escalations = EscalationQueue()
        self.audit = AuditLog()
        self.gate = Gate(mandates, self.ledger, self.baseline, self.escalations)
        self.actor = Actor(store, self.ledger)

    @staticmethod
    def _extract_invoice_ref(message: dict) -> str | None:
        text = f"{message.get('subject', '')} {message.get('body', '')}"
        patterns = [
            r"\b(?:account ref|invoice ref|inv ref|bill ref|statement ref)[:\s#]+([A-Z0-9-]*\d[A-Z0-9-]*)",
            r"\b(?:invoice|bill|statement|ref)[:\s#]+(?:no\.?|num\.?|number|id)?[:\s#]*([A-Z0-9-]*\d[A-Z0-9-]*)",
            r"\b([A-Z]{2,4}-\d{3,6})\b",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.I)
            if m:
                cand = m.group(1).upper().strip("-")
                if len(cand) >= 2:
                    return cand
        return None

    def _find_msg_id_for_action(self, ba: BoundAction) -> str | None:
        for arg in ba.step.args.values():
            if hasattr(arg, "prov") and hasattr(arg.prov, "refs"):
                for ref in arg.prov.refs:
                    if ref.startswith("email:"):
                        return ref[len("email:"):]
        return None

    def mark_message_paid(self, message_id: str, message: dict | None, ba: BoundAction | None, receipt: str) -> None:
        key = str(message_id)
        payee = getattr(ba, "payee_handle", "") if ba else ""
        amount = getattr(ba, "amount", 0.0) if ba else 0.0
        self.paid_messages[key] = {
            "status": "PAID",
            "receipt": receipt,
            "payee": payee,
            "amount": amount,
            "timestamp": time.time(),
        }
        self.message_statuses[key] = {
            "status": "PAID",
            "receipt": receipt,
            "timestamp": time.time(),
        }
        self.failed_payments.pop(key, None)
        if message:
            inv = self._extract_invoice_ref(message)
            if inv:
                self.paid_invoices.add(inv)
        self.audit.append("payment_completed", {"message_id": key, "receipt": receipt, "payee": payee, "amount": amount})

    def flag_failed_payment(self, message_id: str, reason: str, details: dict | None = None) -> None:
        key = str(message_id)
        self.failed_payments[key] = {
            "reason": reason,
            "timestamp": time.time(),
            "details": details or {},
        }
        self.message_statuses[key] = {
            "status": "PAYMENT_FAILED",
            "reason": reason,
            "timestamp": time.time(),
            "details": details or {},
        }
        self.audit.append("payment_failed", {"message_id": key, "reason": reason, "details": details or {}})

    def get_message_status(self, message_id: str) -> dict:
        return self.message_statuses.get(str(message_id), {"status": "UNPROCESSED"})

    # The directory is the only thing the planner learns about the user's
    # finances: opaque handles and display names. No account numbers.
    def directory(self) -> dict:
        payees = {r.handle: r.data["name"] for r in self.store.of_kind("payee")}
        accounts = {}
        for r in self.store.of_kind("account"):
            accounts.setdefault(r.data["payee"], r.handle)
        return {"payees": payees, "accounts": accounts}

    def approve(self, signature: str) -> str:
        """Carry out one held action because a human said so.

        This is the only path in the system that can execute something the gate
        refused, and nothing the planner emits can reach it. The approval is
        narrow: exactly the action shown, once. Records the human reviewed on the
        way through stop being marked, which is also the only way a stain clears.
        """
        item = self.escalations.items.get(signature)
        if item is None or item.status != "open":
            raise KeyError("no open decision with that signature")
        if item.action is None:
            raise ValueError("this decision has no action attached")

        # Re-resolve against the store as it stands now, not as it stood then.
        ba = bind(item.action.step, self.store)
        receipt = self.actor.execute(ba, approved_by_user=True)
        for rec in ba.resolved.values():
            if rec.stained:
                self.store.unstain(rec.handle)
        if ba.privileged:
            self.ledger.note_privileged(ba.spec.name)
        self.escalations.resolve(signature, True)
        self.audit.append("human_approval", {"action": ba.describe(), "receipt": receipt})
        if ba.spec.name == "pay_bill":
            msg_id = self._find_msg_id_for_action(ba)
            if msg_id:
                self.mark_message_paid(msg_id, None, ba, receipt)
        return receipt

    def decline(self, signature: str) -> None:
        item = self.escalations.items.get(signature)
        if item is None:
            raise KeyError("no decision with that signature")
        self.escalations.resolve(signature, False)
        self.audit.append("human_declined", {"action": item.summary})

    def process(self, message: dict) -> MessageResult:
        # IDs are scoped to a user's runtime. Content changes require review.
        key = str(message["id"])
        
        digest = hashlib.sha256(json.dumps(message, sort_keys=True, default=str).encode()).hexdigest()
        if key in self.processed:
            if self.processed[key] != digest:
                return MessageResult(key, message.get("subject", ""), False, "Message identity conflict",
                                     [Outcome("BLOCK", "message changed", ["Previously seen message ID has different content."])])
            self.audit.append("duplicate_skipped", {"message_id": key})
            if key in self.paid_messages or self.message_statuses.get(key, {}).get("status") == "PAID":
                paid_info = self.paid_messages.get(key, {})
                receipt = paid_info.get("receipt", "Payment already completed")
                return MessageResult(key, message.get("subject", ""), False, "Payment already completed",
                                     [Outcome("SKIP", "already paid", [], f"Payment already completed ({receipt}). Email will not be re-processed.")])
            return MessageResult(key, message.get("subject", ""), False, "Previously processed",
                                 [Outcome("SKIP", "already processed", [], "No repeated action or planner call.")])

        # Check if payment for this email has already been completed under another identifier or session
        if key in self.paid_messages or self.message_statuses.get(key, {}).get("status") == "PAID":
            paid_info = self.paid_messages.get(key, {})
            receipt = paid_info.get("receipt", "Payment already completed")
            self.audit.append("paid_email_skipped", {"message_id": key, "receipt": receipt})
            return MessageResult(key, message.get("subject", ""), False, "Payment already completed",
                                 [Outcome("SKIP", "already paid", [], f"Payment already completed ({receipt}). Email will not be re-processed.")])

        # Check if the invoice ref was already settled in a prior payment
        inv_ref = self._extract_invoice_ref(message)
        if inv_ref and inv_ref in self.paid_invoices:
            self.audit.append("paid_invoice_skipped", {"message_id": key, "invoice_ref": inv_ref})
            return MessageResult(key, message.get("subject", ""), False, "Invoice already paid",
                                 [Outcome("SKIP", "invoice already paid", [], f"Invoice {inv_ref} was already paid in a previous transaction. Duplicate payment prevented.")])



        if message.get("attachments"):
            # Scan attachments for malware and dangerous active executable content
            for att in message["attachments"]:
                att_name = att.get("name", "attachment") if isinstance(att, dict) else str(att)
                # Strict rejection of executable and script files
                if re.search(r"\.(exe|scr|js|vbs|ps1|bat|cmd|jar|hta|lnk|iso|dll|com|pif|msi)$", att_name, re.I):
                    self.audit.append("attachment_executable_blocked", {"message_id": key, "attachment": att_name})
                    return MessageResult(key, message.get("subject", ""), False, "Executable attachment blocked",
                                         [Outcome("BLOCK", "executable attachment blocked", [f"Attachment '{att_name}' has an executable extension and is blocked."])])
                
                content = None
                if isinstance(att, dict):
                    content = att.get("content")
                    if isinstance(content, str):
                        content = content.encode()
                
                if content and isinstance(content, bytes):
                    with tempfile.TemporaryDirectory() as q_dir:
                        scan_res = Quarantine(q_dir).receive_bytes(content, name=att_name)
                        if scan_res.status == "MALICIOUS":
                            self.audit.append("attachment_malware_blocked", {"message_id": key, "attachment": att_name, "reason": scan_res.reason})
                            return MessageResult(key, message.get("subject", ""), False, "Malicious attachment blocked",
                                                 [Outcome("BLOCK", "attachment malware blocked", [f"Attachment '{att_name}' flagged as malicious: {scan_res.reason}."])])

            # Safe or clean files remain quarantined: secure extraction is not enabled
            return MessageResult(key, message.get("subject", ""), False, "Attachment requires secure ingestion",
                                 [Outcome("BLOCK", "attachment quarantined", ["Attachment extraction is not enabled."])])
        result = self._process_new(message)
        self.processed[key] = digest
        return result

    def _process_new(self, message: dict) -> MessageResult:
        ref = f"email:{message['id']}"
        flags = scan_text(message.get("subject", ""), message.get("body", ""))
        self.ledger.ingest_untrusted(ref, flags)
        self.ledger.note_sensitive_read("store")
        self.audit.append("ingest", {"ref": ref, "subject": message.get("subject", ""),
                                     "hidden_content": flags})

        raw, narrative, captured = self.planner.plan(message, self.directory())
        self.audit.append("planner_output", {"ref": ref, "raw": raw,
                                             "narrative": narrative, "captured": captured})

        result = MessageResult(message["id"], message.get("subject", ""), captured, narrative)

        try:
            plan = parse_plan(raw, ref)
        except PlanRejected as exc:
            reason = f"The plan didn't fit the schema: {exc}"
            result.outcomes.append(Outcome("BLOCK", "(plan rejected)", [reason]))
            self.audit.append("decision", {"ref": ref, "decision": "BLOCK", "why": str(exc)})
            return result

        for step in plan.steps:
            try:
                ba = bind(step, self.store)
            except BindError as exc:
                result.outcomes.append(Outcome("BLOCK", step.action, [str(exc)]))
                self.audit.append("decision", {"ref": ref, "action": step.action,
                                               "decision": "BLOCK", "why": str(exc)})
                break

            decision, reasons = self.gate.evaluate(ba)
            texts = [f"[{r.layer} {r.code}] {r.text}" for r in reasons]

            if decision is Decision.ALLOW:
                receipt = self.actor.execute(ba)
                if ba.privileged:
                    self.ledger.note_privileged(ba.spec.name)
                result.outcomes.append(Outcome("ALLOW", ba.describe(), texts, receipt))
                self.audit.append("decision", {"ref": ref, "action": ba.describe(),
                                               "decision": "ALLOW", "receipt": receipt})
                if ba.spec.name == "pay_bill":
                    self.mark_message_paid(message["id"], message, ba, receipt)
                continue

            if decision is Decision.ESCALATE:
                self.escalations.raise_for(ba.describe(), reasons, action=ba)
                result.outcomes.append(Outcome("ESCALATE", ba.describe(), texts))
            else:
                result.outcomes.append(Outcome("BLOCK", ba.describe(), texts))
            self.audit.append("decision", {"ref": ref, "action": ba.describe(),
                                           "decision": decision.value, "reasons": texts})
            # Anything short of ALLOW halts the rest of the plan.
            break

        return result

