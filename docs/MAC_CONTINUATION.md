# Mac continuation — 24 October 2026

Continued from the Desktop folder supplied after the original ZIP review. Existing seeds and API key were preserved; no replacement identities were generated.

## Verified here

- Python 3.13.9 and all declared dependencies installed in a local virtual environment.
- Original 36 tests pass; expanded suite: 48 tests pass.
- Saved ASI:One API key verified using one synthetic Acme invoice; live model returned a valid gated plan.
- All three agents started with their existing identities, published manifests and registered with the Almanac API. Local `/health` returns `ok`, payments false.
- Public orchestrator profile shows Active, ASI Available, Mailbox Build.

## Added in this continuation

- SQLite-backed JSON snapshots persist demo payments, trusted records, provenance stains, approvals, audit chain and processed message identities across restarts.
- Serialized transactions protect concurrent processing; repeat messages skip the planner and effects. Changed content under a reused ID is blocked.
- Inbox runs no longer reset the demo state. The explicit reset command still resets the demo and must not be used for live payment records.
- Pasted messages have stable content-derived identifiers.
- Summary cards show skipped and blocked messages; Bank outages no longer produce an unqualified successful fallback receipt.
- Attachment-bearing messages fail closed before planning. A quarantine storage/scanner adapter accepts byte streams, applies size/type checks, interprets ClamAV exit codes and never releases or opens files.
- Regression tests cover restart, concurrency, owner isolation, persisted approvals and stains, and quarantine/scanner failure cases.

## Important limits

The database transaction protects local simulated effects. It is not an exactly-once real banking implementation. Different emails for the same invoice still need invoice-level identity matching. The Reader remains a fixture/paste reader; it does not fetch a personal mailbox or apply real email labels. Failed-payment email flagging is not complete.

ClamAV is not installed on this Mac. Scanner tests use mocks; no real antivirus effectiveness claim is made. Every received file remains quarantined, including scanner-passed files. Signature freshness checks, active-document inspection, isolated extraction and real download/mailbox integration must be completed before files can be released. No unsafe attachment is opened as a fallback.

ASI:One browser sign-in and an end-to-end chat test remain outstanding. The live API test does not prove UI card rendering or mailbox conversation delivery. No submission, public shared chat, demo video or real payment has been made here. Agentverse on-chain contract registration reports insufficient funds; API registration succeeds. Do not fund a wallet merely to suppress that warning.

## Run

On the Mac, use the workspace Python environment described in the handoff. For a fresh checkout, select Python 3.10–3.13, run `python -m venv .venv`, install requirements, and preserve the existing private `.env`. Do not copy the Windows `.venv` to macOS or regenerate the seeds.

Run `.venv/bin/python -m pytest -q`, `.venv/bin/python scripts/check_setup.py --live`, and `.venv/bin/python run_all.py` after environment setup. Only run one deployment of the same agent identities at a time. A sleeping/stopped Mac will not keep the agents available for judging.
