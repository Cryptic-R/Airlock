# Live chat verification — 31 October 2026

Changes are isolated on `codex/asi-chat-workflow`; `main` is unchanged.

## Verified

- All three original mailbox identities start and register through the Almanac API.
- ASI:One delivered `Run my inbox` to Airlock; logs show Reader and Bank hops.
- ASI:One rendered the summary with simulated payments, gate reasons and audit status.
- Separate review messages were not visible in the chat. Decisions now appear as
  buttons inside the summary card.
- The Approve button submitted successfully, and Airlock returned a Bank receipt
  for the simulated 412.00 water bill, explicitly stating no bank transfer occurred.
- Submitted cards become disabled; remaining decisions are now reissued after each
  decline or non-token approval. A regression test verifies this behavior.
- Merged suite: **62 tests pass**, including the repository's persistence,
  duplicate-message, download-quarantine and payment-failure tests.

## Runtime notes

Live LLM outputs vary: the model may warn about an email instead of proposing an
action that needs a gate decision. Offline red-team counts are deterministic;
they are not a guarantee of identical live cards. The planner timeout is now
20 seconds with no retries, and the token allowance is 1500. Invalid output
continues to fall back through the same schema and deterministic gate.

Token payments remain disabled. No real bill was paid. The local agents require
the machine and processes to remain running.

## Submission still pending

The chat URL is a private working conversation, not a verified public share:
https://asi1.ai/chat/0c5a556c-3dc5-438c-aaaf-f4840217f508

Public share, demo video, team/member details and final submission confirmation
are not yet supplied. The original checklist dates are in the past; eligibility
or late submission must be verified with the event dashboard.
