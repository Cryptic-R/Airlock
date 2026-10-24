"""Bank agent: carries out the side effect of a gate-approved action.

It accepts only a typed ExecRequest describing an action the orchestrator's gate
already approved -- it never sees the email, the planner's reasoning, or any free
text. Here it confirms settlement; in production this is where a real banking or
scheduling API would be called.
"""

import os

from uagents import Agent, Context, Protocol

from common.config import BANK_PORT, BANK_SEED, ORCHESTRATOR_ADDRESS
from common.models import ExecRequest, ExecResult

agent = Agent(name=os.getenv("BANK_NAME", "airlock_bank"), seed=BANK_SEED,
              port=BANK_PORT, mailbox=True, publish_agent_details=True)
proto = Protocol(name="AirlockBank", version="1.0.0")


@proto.on_message(ExecRequest, replies=ExecResult)
async def on_exec(ctx: Context, sender: str, req: ExecRequest):
    if sender != ORCHESTRATOR_ADDRESS:
        await ctx.send(sender, ExecResult(job_id=req.job_id, ok=False, error="Unauthorised sender"))
        return
    ctx.logger.info(f"[{req.job_id}] exec {req.action} {req.receipt_hint}")
    try:
        if req.action == "pay_bill":
            receipt = f"Demo ledger confirmation: {req.receipt_hint}. Ref BK-{req.job_id}. No bank transfer was made."
        else:
            receipt = req.receipt_hint or f"{req.action} carried out. Ref BK-{req.job_id}."
        await ctx.send(sender, ExecResult(job_id=req.job_id, ok=True, receipt=receipt))
    except Exception as exc:
        ctx.logger.exception("exec failed")
        await ctx.send(sender, ExecResult(job_id=req.job_id, ok=False, error=str(exc)))


agent.include(proto, publish_manifest=True)


@agent.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info(f"Airlock Bank ready: {agent.address}")


if __name__ == "__main__":
    agent.run()
