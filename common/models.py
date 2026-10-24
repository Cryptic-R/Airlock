"""Agent-to-agent messages. JSON string payloads keep the protocol digest stable."""

from uagents import Model


# Orchestrator -> Reader: fetch/parse an inbox message or the whole demo inbox.
class ReadRequest(Model):
    job_id: str
    mode: str            # "inbox" (return demo inbox) | "parse" (parse raw_text)
    raw_text: str = ""


class ReadResult(Model):
    job_id: str
    ok: bool
    error: str = ""
    messages_json: str = "[]"   # list of {id, from, subject, body}


# Orchestrator -> Bank: carry out one gate-approved action's side effect.
class ExecRequest(Model):
    job_id: str
    action: str                 # e.g. "pay_bill"
    receipt_hint: str           # human description computed by the gate layer
    amount: float = 0.0
    payee_name: str = ""


class ExecResult(Model):
    job_id: str
    ok: bool
    error: str = ""
    receipt: str = ""
