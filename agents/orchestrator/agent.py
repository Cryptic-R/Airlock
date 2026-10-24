"""Airlock orchestrator: the agent users talk to on ASI:One.

Owns the Airlock engine (planner + deterministic gate + actor), speaks the Agent
Chat Protocol with Interactive Cards, and the Agent Payment Protocol for settling
approved bills.
"""

import os

from uagents import Agent, Context, Model

from agents.orchestrator.chat import chat_proto
from agents.orchestrator.payment import payment_proto, set_agent_wallet
from common.config import (
    BANK_ADDRESS,
    ENABLE_PAYMENTS,
    ORCHESTRATOR_PORT,
    ORCHESTRATOR_SEED,
    READER_ADDRESS,
)

agent = Agent(
    name=os.getenv("ORCHESTRATOR_NAME", "airlock"),
    seed=ORCHESTRATOR_SEED,
    port=ORCHESTRATOR_PORT,
    mailbox=True,
    publish_agent_details=True,
    handle_messages_concurrently=False,
)

agent.include(chat_proto, publish_manifest=True)
if ENABLE_PAYMENTS:
    agent.include(payment_proto, publish_manifest=True)
set_agent_wallet(agent.wallet)


class Health(Model):
    status: str
    agent: str
    reader_agent: str
    bank_agent: str
    payments: bool


@agent.on_rest_get("/health", Health)
async def health(ctx: Context) -> Health:
    return Health(status="ok", agent=agent.address, reader_agent=READER_ADDRESS,
                  bank_agent=BANK_ADDRESS, payments=ENABLE_PAYMENTS)


@agent.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info(f"Airlock orchestrator: {agent.address}")
    ctx.logger.info(f"wallet: {agent.wallet.address()}  payments={'on' if ENABLE_PAYMENTS else 'off'}")
    ctx.logger.info(f"reader: {READER_ADDRESS} | bank: {BANK_ADDRESS}")


if __name__ == "__main__":
    agent.run()
