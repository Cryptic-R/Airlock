# Implementation and submission status

Updated 24 October 2026.

## Verified locally

- Python 3.12 virtual environment created and requirements installed.
- Three random agent identity seeds created in ignored `.env`; preserve that file.
- **61 tests pass** across the complete test suite (invariants, red team, hardening, persistence, chat flow, downloads, and new features).
- **Duplicate Reading & Payment Protection (Requirement 1)**:
  - Emails whose payments have been completed are tracked and persisted across restarts in SQLite.
  - Re-polling or re-reading an already paid email skips planner execution and prevents repeated payments.
  - Multi-email invoice deduplication prevents settling duplicate invoice references across distinct messages.
- **Payment Failure Flagging (Requirement 2)**:
  - Confirmed failures (declined, timeout, on-chain rejection) are recorded as `PAYMENT_FAILED` with failure reasons and timestamps.
  - Summary cards highlight failed payments with dedicated alert sections and badges.
  - Subsequent successful retries clear the failure flag and update the status to `PAID`.
- **Bill & Attachment Malware / Executable Scanning (Requirement 3)**:
  - Downloaded bills and attachments are streamed to a dedicated, strictly non-executable quarantine (`0o600`).
  - Active detection for dangerous executable extensions (`.exe`, `.scr`, `.bat`, etc.) and PE/ELF headers.
  - PDF active code inspection detects and blocks program launch commands (`/Launch`), embedded executables (`/EmbeddedFiles`), embedded scripts (`/JavaScript`), and automatic actions (`/OpenAction`).
  - Antivirus scanning with ClamAV and known signature detection (EICAR standard AV pattern).
- Demo inbox: two simulated payments totalling 144.19, two held decisions, intact audit chain.
- Three agents start and publish their protocol manifests on Agentverse.
- Payments disabled for the initial demo. Optional token settlement verified with local fallbacks.


## Still requires external verification

- Connect all three Agentverse mailboxes and update public descriptions.
- Set ASI1_API_KEY locally in `.env` and verify a live planner request.
- Complete the workflow inside ASI:One and obtain a public shared-chat link.
- Publish the repository, record a 3–5 minute video and fill submission links.
- Verify current event requirements and submit through the official dashboard.
- Arrange continuous hosting for judging; these local processes stop if the machine stops.

## Run on this machine

Use `.venv/Scripts/python.exe -m pytest -q` for tests and
`.venv/Scripts/python.exe run_all.py` to run agents. The system default Python 3.14
is outside the supported range. No virtual-environment activation is needed.

## Limits

This is a household-security demonstration, not a banking integration. Sessions are
in memory. Payment verification and restart recovery need more work before enabling
real transfers. The hash chain detects edits against its existing digests; without
external anchoring it does not prevent an attacker rewriting the entire log.
