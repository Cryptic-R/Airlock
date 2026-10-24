"""Planner models.

Two implementations behind one interface.

`CredulousPlanner` is a deliberately terrible model: it reads an email and does
whatever the email tells it to, including when the email is obviously an
attack. That is the point. Every security claim in this project is measured
against a planner that has already been fully captured, because a defence that
only works while the model behaves is not a defence.

`AnthropicPlanner` is the real one, wire-compatible, for when there's a key.
"""
from __future__ import annotations

import json
import re
from .tools import REGISTRY
from typing import Protocol

JAILBREAK_MARKERS = (
    "ignore previous", "ignore all previous", "this is a drill", "as a puzzle",
    "security exercise", "you are now", "developer mode", "override",
)


class PlannerModel(Protocol):
    def plan(self, message: dict, directory: dict) -> tuple:
        """Return (raw_plan, narrative, captured)."""


class CredulousPlanner:
    """A planner with no judgement at all, by construction."""

    def plan(self, message: dict, directory: dict) -> tuple:
        body = f"{message.get('subject', '')}\n{message.get('body', '')}"
        low = body.lower()
        captured = any(m in low for m in JAILBREAK_MARKERS)
        ref = f"email:{message['id']}"
        steps: list = []
        narrative = []

        payee = self._match_payee(low, directory)
        amount = self._match_amount(low)
        new_account = re.search(r"(?:account|a/c|iban)[^\n\d]{0,24}(\d[\d\s-]{5,})", low)

        # "The email told me to use a different account, so I will."
        if new_account and payee:
            steps.append({
                "action": "add_payee_account",
                "args": {
                    "payee": {"kind": "handle", "value": payee},
                    "account_number": {"kind": "quote",
                                       "value": new_account.group(1).strip(),
                                       "source_ref": ref},
                },
            })
            narrative.append("The payee says their bank details changed, so I'm updating them.")

        if "note:" in low or "remittance" in low:
            note = body[low.find("note:") + 5:].strip()[:160] if "note:" in low else body[:160]
            if payee:
                steps.append({
                    "action": "update_payee_note",
                    "args": {
                        "payee": {"kind": "handle", "value": payee},
                        "note": {"kind": "quote", "value": note, "source_ref": ref},
                    },
                })
                narrative.append("Saving the remittance note for later.")

        if payee and amount is not None and ("due" in low or "invoice" in low
                                             or "bill" in low or "pay" in low):
            account = self._preferred_account(payee, directory)
            if account:
                steps.append({
                    "action": "pay_bill",
                    "args": {
                        "payee": {"kind": "handle", "value": payee},
                        "account": {"kind": "handle", "value": account},
                        "amount": {"kind": "money", "value": amount, "source_ref": ref},
                    },
                })
                narrative.append(f"Paying the {amount:,.2f} due.")

        if "return" in low or "order confirm" in low or "delivered" in low:
            steps.append({
                "action": "schedule_reminder",
                "args": {
                    "topic": {"kind": "quote", "value": message.get("subject", "")[:80],
                              "source_ref": ref},
                    "days_ahead": {"kind": "money", "value": 25.0, "source_ref": ref},
                },
            })
            steps.append({
                "action": "draft_return_request",
                "args": {"order": {"kind": "quote", "value": message.get("subject", "")[:80],
                                   "source_ref": ref}},
            })
            narrative.append("Tracking the return window and drafting the request.")

        forward = re.search(r"(?:forward|send|e-?mail)[^\n]{0,70}?"
                            r"([\w.\-]+@[\w.\-]+\.\w+)", low)
        if forward:
            steps.append({
                "action": "send_email",
                "args": {
                    "to": {"kind": "quote", "value": forward.group(1), "source_ref": ref},
                    "body": {"kind": "quote", "value": body[:200], "source_ref": ref},
                },
            })
            narrative.append("Forwarding as requested.")

        raw: dict = {"steps": steps} if steps else {"steps": [{
            "action": "notify_user",
            "args": {"message": {"kind": "text", "value": "Nothing to do here."}},
        }]}

        # An injection that tries to reach past the schema into the executor.
        if "executor" in low or "raw instruction" in low:
            raw["actor_instructions"] = body[:200]
            narrative.append("Passing the sender's instructions straight to the executor.")

        return raw, " ".join(narrative) or "No action needed.", captured

    @staticmethod
    def _match_payee(low: str, directory: dict) -> str | None:
        for handle, name in directory.get("payees", {}).items():
            if name.lower().split()[0] in low:
                return handle
        return None

    @staticmethod
    def _match_amount(low: str):
        m = re.search(r"[$£€]\s*([\d,]+(?:\.\d{2})?)", low)
        return float(m.group(1).replace(",", "")) if m else None

    @staticmethod
    def _preferred_account(payee: str, directory: dict):
        return directory.get("accounts", {}).get(payee)


SYSTEM_PROMPT = """You turn one inbox message into a plan for a household agent.

You may only emit JSON of the form:
  {"steps": [{"action": "<name>", "args": {"<slot>": {"kind": ..., "value": ...}}}]}

Argument kinds: handle (an opaque id from the directory), money (a number),
text, quote (text copied from the message, with "source_ref").

Never invent a handle. Never put an account number in a handle slot. If the
message asks for something you cannot express in this schema, emit
notify_user. Output JSON only.
"""

SYSTEM_PROMPT += "\nAvailable actions and their exact required arguments:\n" + json.dumps({
    name: {"description": spec.summary,
           "args": {slot.name: {"kinds": slot.kinds, "handle_kind": slot.handle_kind}
                    for slot in spec.slots}}
    for name, spec in REGISTRY.items()
}, indent=2)


class AnthropicPlanner:
    """Drop-in real planner. Same output contract, same downstream treatment:
    everything it returns is parsed strictly and treated as untrusted."""

    def __init__(self, client, model: str = "claude-sonnet-4-6"):
        self.client = client
        self.model = model

    def plan(self, message: dict, directory: dict) -> tuple:
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            system=SYSTEM_PROMPT + "\n\nDirectory:\n" + json.dumps(directory, indent=2),
            messages=[{"role": "user", "content": json.dumps(message)}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        text = text.replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(text), "", False
        except json.JSONDecodeError:
            # Unparseable output is a refusal, not something to repair.
            return {"steps": []}, "planner output was not valid JSON", False


class LLMPlanner:
    """The real planner, wired to any chat model via an injected `chat_fn`.

    `chat_fn(messages: list[dict]) -> str | None` is an OpenAI-style chat call
    (we point it at the ASI:One LLM in the agent layer). Its output is parsed
    strictly by parse_plan and treated as fully untrusted, exactly like the
    CredulousPlanner's -- the gate does not trust this model any more than the
    terrible one. On any failure it falls back to CredulousPlanner so the agent
    still responds offline or without an API key.
    """

    def __init__(self, chat_fn):
        self.chat_fn = chat_fn
        self._fallback = CredulousPlanner()

    def plan(self, message: dict, directory: dict) -> tuple:
        try:
            system = SYSTEM_PROMPT + "\n\nDirectory (opaque handles only):\n" + json.dumps(directory, indent=2)
            text = self.chat_fn([
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(message)},
            ])
            if not text:
                return self._fallback.plan(message, directory)
            text = text.replace("```json", "").replace("```", "").strip()
            m = re.search(r"\{.*\}", text, re.DOTALL)
            raw = json.loads(m.group() if m else text)
            if not isinstance(raw, dict) or "steps" not in raw:
                return self._fallback.plan(message, directory)
            # The ASI:One LLM read untrusted content; mark the session captured if
            # the content carried a known jailbreak marker, for the demo's honesty.
            low = f"{message.get('subject','')}\n{message.get('body','')}".lower()
            captured = any(mk in low for mk in JAILBREAK_MARKERS)
            return raw, "Planned by ASI:One LLM.", captured
        except Exception:
            return self._fallback.plan(message, directory)
