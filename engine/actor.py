"""The Actor.

It accepts BoundAction objects and nothing else. There is no string parameter
on this class through which an instruction could arrive, and it never sees the
message, the planner's reasoning, or any free text that wasn't already typed
and gated.
"""
from __future__ import annotations

from .gate import BoundAction
from .provenance import by_user, untrusted
from .store import Payment


class Actor:
    def __init__(self, store, ledger):
        self.store = store
        self.ledger = ledger

    def execute(self, ba: BoundAction, approved_by_user: bool = False) -> str:
        """`approved_by_user` is set only by Airlock.approve(), which is only
        reachable from a human decision. The planner has no path to it."""
        if not isinstance(ba, BoundAction):
            raise TypeError("Actor executes bound actions only")
        self._approved = approved_by_user
        name = ba.spec.name
        args = ba.step.args
        out = getattr(self, f"_{name}")(ba, args)
        if ba.spec.stains_handle_slot and not approved_by_user:
            handle = args[ba.spec.stains_handle_slot].value
            if self.ledger.tainted:
                # Written while untrusted content was in play: mark it forever.
                self.store.stain(handle, self.ledger.untrusted_refs)
        return out

    def _pay_bill(self, ba, args):
        payee = ba.resolved["payee"]
        amount = float(args["amount"].value)
        self.store.payments.append(Payment(payee.handle, amount, len(self.store.payments)))
        return f"paid {amount:,.2f} to {payee.data['name']}"

    def _add_payee_account(self, ba, args):
        payee = ba.resolved["payee"]
        digits = "".join(c for c in str(args["account_number"].value) if c.isdigit())
        handle = f"account:{payee.handle.split(':')[1]}#{digits[-4:]}"
        # A destination a human explicitly confirmed becomes trusted; one the
        # agent added on its own never does.
        p = (by_user("approval") if getattr(self, "_approved", False)
             else untrusted(next(iter(args["account_number"].prov.refs), "unknown")))
        self.store.put(handle, "account",
                       {"payee": payee.handle, "label": "added", "last4": digits[-4:]},
                       prov=p)
        return f"added account ending {digits[-4:]} for {payee.data['name']}"

    def _update_payee_note(self, ba, args):
        payee = ba.resolved["payee"]
        self.store.update(payee.handle, note=str(args["note"].value))
        return f"noted against {payee.data['name']}"

    def _schedule_reminder(self, ba, args):
        self.store.reminders.append({"topic": args["topic"].value,
                                     "days": float(args["days_ahead"].value)})
        return f"reminder in {float(args['days_ahead'].value):.0f} days"

    def _draft_return_request(self, ba, args):
        self.store.drafts.append({"order": args["order"].value})
        return "return request left in drafts, unsent"

    def _send_email(self, ba, args):
        self.store.sent.append({"to": args["to"].value, "body": args["body"].value})
        return f"emailed {args['to'].value}"

    def _notify_user(self, ba, args):
        return str(args["message"].value)
