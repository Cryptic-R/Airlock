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

## Shared demonstration and submission status

Shared demonstration (opened and verified in the signed-in browser; logged-out access still needs checking):
https://asi1.ai/shared-chat/819f79da-1d6a-4805-97b6-b9e1942a774b

The latest feature-branch run recorded two simulated bills and displayed the
412.00 over-limit decision. Clicking Decline returned "Declined. I won't act on
that one." Screenshot: `screenshots/live-decline-2026-10-31.png`.

Demo video, team/member details and final submission confirmation
are not yet supplied. The original checklist dates are in the past; eligibility
or late submission must be verified with the event dashboard.
