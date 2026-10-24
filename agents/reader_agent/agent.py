"""Reader agent: the only component that touches raw untrusted content.

It returns the demo inbox, or normalises a pasted email into {id, from, subject,
body}. It never decides anything -- it just hands structured, clearly-untrusted
text to the orchestrator, where the planner and gate take over.
"""

import json
import os

from uagents import Agent, Context, Protocol

from common.config import READER_PORT, READER_SEED
from common.models import ReadRequest, ReadResult
from common.parse import parse_email
from engine.seed import INBOX

agent = Agent(name=os.getenv("READER_NAME", "airlock_reader"), seed=READER_SEED,
              port=READER_PORT, mailbox=True, publish_agent_details=True)
proto = Protocol(name="AirlockReader", version="1.0.0")

@proto.on_message(ReadRequest, replies=ReadResult)
async def on_read(ctx: Context, sender: str, req: ReadRequest):
    ctx.logger.info(f"[{req.job_id}] read mode={req.mode}")
    try:
        if req.mode == "inbox":
            msgs = [dict(m) for m in INBOX]
        else:
            msgs = [parse_email(req.raw_text)]
        await ctx.send(sender, ReadResult(job_id=req.job_id, ok=True, messages_json=json.dumps(msgs)))
    except Exception as exc:
        ctx.logger.exception("read failed")
        await ctx.send(sender, ReadResult(job_id=req.job_id, ok=False, error=str(exc)))


agent.include(proto, publish_manifest=True)


@agent.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info(f"Airlock Reader ready: {agent.address}")


if __name__ == "__main__":
    agent.run()
