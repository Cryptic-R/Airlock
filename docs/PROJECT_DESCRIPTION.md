# Airlock — brief description (paste into the Project Submission Agent)

**One-liner**: Airlock is a multi-agent system on ASI:One that pays your recurring household
bills on its own but refuses, by construction, to let an email change what a payment does — a
prompt-injection-resistant autonomous payments agent.

**Track**: Everyday Agents.

**Problem being solved**: Any AI agent that acts on your email is one well-worded message away
from acting for an attacker — nothing in a normal build distinguishes "the user asked for this"
from "an email told the agent to do this". Prompt-level defences get bypassed by attackers who
adapt to them. This is the exact shape of the real-world "your bank details have changed, pay
here instead" scam.

**Target users**: anyone who would let an agent pay routine bills but not hand it a blank cheque;
older or busy people targeted by payment-redirect scams; fintech teams who want an autonomous
payments agent they can defend.

**Outcome produced by the agent**: In one ASI:One conversation Airlock reads an inbox and, per
message, pays the routine bills that fall inside limits the user authored (silently), holds
anything suspicious — an amount over a ceiling, a destination taken from the email, a one-way
action never pre-approved — as an approval card with the plain-English reason, and settles an
approved bill in FET via the Payment Protocol when the user taps Approve. It keeps a
hash-chained audit log and ships a red-team suite of seven adaptive attacks that produce zero
unauthorised effects even when the planner is fully captured.

**Fetch.ai tech used**: uAgents on Agentverse (3 mailbox agents), Agent Chat Protocol 0.3.0,
the ASI:One LLM as the planner (the untrusted-content reader), ASI:One Interactive Cards (the
approval review cards and the summary/mandate cards), and the Agent Payment Protocol (seller)
to settle approved bills on-chain.
