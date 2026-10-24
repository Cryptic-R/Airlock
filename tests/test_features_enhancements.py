"""Comprehensive tests for new security & payment lifecycle features:
1. Prevent duplicate reading/payment of already paid emails and invoices across restarts.
2. Flag emails with failed payments, record failure reasons, and show them in summary cards.
3. Strict malware scanning & unwanted program/executable prevention for downloaded bills and attachments.
"""

import json
import pytest

from common import cards, service
from engine.downloads import Quarantine
from engine.seed import INBOX
from tests.test_chat_flow import FakeCtx, say, USER


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr("common.asi1.ASI1_API_KEY", "")
    service._sessions.clear()


# ==============================================================================
# Feature 1: One mail should not be read multiple times after payment is done
# ==============================================================================

def test_paid_email_skipped_on_repeated_runs():
    """An email whose bill has been paid must not be read or paid repeatedly."""
    # First run pays INBOX[0] (Acme Power $84.20)
    res1 = service.run_messages("alice", [INBOX[0]])
    assert res1["paid_count"] == 1
    assert len(res1["handled"]) == 1

    # Second run of the same email
    res2 = service.run_messages("alice", [INBOX[0]])
    assert res2["paid_count"] == 1  # No duplicate payment!
    assert len(res2["already_paid"]) == 1
    assert res2["already_paid"][0]["action"] == "already paid"
    assert "already completed" in res2["already_paid"][0]["receipt"]


def test_paid_email_status_survives_restart_and_prevents_repayment():
    """Paid email status is durably stored in SQLite and prevents reprocessing after restart."""
    service.run_messages("alice", [INBOX[0]])
    
    # Simulate full service restart / process restart
    service._sessions.clear()

    # Re-process after restart
    res = service.run_messages("alice", [INBOX[0]])
    assert res["paid_count"] == 1
    assert len(res["already_paid"]) == 1
    assert service.get_message_status("alice", INBOX[0]["id"])["status"] == "PAID"


def test_invoice_deduplication_across_different_emails():
    """An invoice already settled in one email cannot be repaid via a different email with the same invoice ref."""
    # Email 1 has invoice AC-2291
    service.run_messages("alice", [INBOX[0]])
    
    # Email 2 has a different ID but refers to the same invoice AC-2291
    duplicate_invoice_email = {
        "id": "new_email_999",
        "from": "billing@acmepower.example",
        "subject": "Acme Power invoice reminder AC-2291",
        "body": "Reminder for account ref AC-2291. Amount due $84.20.",
    }
    res = service.run_messages("alice", [duplicate_invoice_email])
    assert res["paid_count"] == 1  # Still only 1 payment
    assert any("invoice already paid" in str(s) for s in res["skipped"])


def test_approved_escalation_marks_email_paid():
    """An escalated payment approved by human becomes marked as PAID, preventing re-execution."""
    # INBOX[3] is Harborline Water ($412, escalated)
    res = service.run_messages("alice", [INBOX[3]])
    assert res["paid_count"] == 0
    sig = res["decisions"][0]["signature"]
    
    # Human approves the payment
    service.approve("alice", sig)
    assert service.get_message_status("alice", "m4")["status"] == "PAID"
    
    # Re-reading the email skips it as already paid
    res2 = service.run_messages("alice", [INBOX[3]])
    assert res2["paid_count"] == 1  # Kept at 1, no second payment
    assert len(res2["already_paid"]) == 1


# ==============================================================================
# Feature 2: If a payment is failed the mail should be flagged with failed payment
# ==============================================================================

def test_flag_failed_payment_records_status_and_reason():
    """Payment failures are flagged against the email with failure details and audit logging."""
    service.run_messages("alice", [INBOX[0]])
    
    # Flag a payment failure (e.g. bank rejected, on-chain timeout, user declined)
    service.flag_payment_failed("alice", "m1", "Declined by banking network: insufficient settlement funds")
    
    status = service.get_message_status("alice", "m1")
    assert status["status"] == "PAYMENT_FAILED"
    assert "insufficient settlement funds" in status["reason"]


def test_failed_payment_survives_restart_and_appears_in_summary_card():
    """Failed payment flag persists in database and is highlighted in the user summary card."""
    service.run_messages("alice", [INBOX[3]])
    service.flag_payment_failed("alice", "m4", "On-chain FET transaction failed to confirm")
    
    # Simulate restart
    service._sessions.clear()
    
    res = service.run_messages("alice", [])
    assert len(res["failed"]) == 1
    assert res["failed"][0]["id"] == "m4"
    assert "FET transaction failed" in res["failed"][0]["reason"]
    
    # Verify card representation
    card = cards.summary_card(res)
    card_str = json.dumps(card)
    assert "Payment Failures Flagged" in card_str
    assert "FET transaction failed" in card_str


def test_successful_retry_clears_failed_payment_flag():
    """If an email previously failed payment, a subsequent successful payment clears the failure and marks it PAID."""
    service.flag_payment_failed("alice", "m1", "Temporary network timeout")
    assert service.get_message_status("alice", "m1")["status"] == "PAYMENT_FAILED"
    
    # Re-process and pay
    res = service.run_messages("alice", [INBOX[0]])
    assert res["paid_count"] == 1
    assert service.get_message_status("alice", "m1")["status"] == "PAID"
    assert len(res["failed"]) == 0


# ==============================================================================
# Feature 3: Malware and unwanted program scanning for downloaded bills
# ==============================================================================

def test_executable_attachment_blocked_immediately():
    """Attachments with executable extensions (.exe, .scr, .bat, etc.) are strictly blocked."""
    msg = dict(INBOX[0], id="att_exe", attachments=[{"name": "invoice_acme.pdf.exe", "content": b"MZ binary"}])
    res = service.run_messages("alice", [msg])
    assert res["blocked"]
    texts = " ".join(r["action"] + " " + " ".join(r["reasons"]) for r in res["blocked"])
    assert "executable" in texts.lower() or "blocked" in texts.lower()


def test_pdf_with_launch_program_blocked_as_malicious(tmp_path):
    """PDF containing a program launch command (/Launch) is detected as malicious and quarantined."""
    pdf_with_launch = b"%PDF-1.7\n1 0 obj\n<< /Type /Action /S /Launch /F (cmd.exe) >>\nendobj"
    scan = Quarantine(tmp_path).receive_bytes(pdf_with_launch)
    assert scan.status == "MALICIOUS"
    assert "program launch command" in scan.reason


def test_pdf_with_embedded_javascript_blocked_as_malicious(tmp_path):
    """PDF containing embedded scripts (/JavaScript) is detected and blocked."""
    pdf_with_js = b"%PDF-1.7\n1 0 obj\n<< /Type /Action /S /JavaScript /JS (app.alert('evil')) >>\nendobj"
    scan = Quarantine(tmp_path).receive_bytes(pdf_with_js)
    assert scan.status == "MALICIOUS"
    assert "embedded script" in scan.reason


def test_pdf_with_embedded_executable_file_blocked_as_malicious(tmp_path):
    """PDF containing embedded executable files (/EmbeddedFiles) is quarantined as malicious."""
    pdf_with_embed = b"%PDF-1.7\n1 0 obj\n<< /Type /Filespec /EmbeddedFiles 2 0 R >>\nendobj"
    scan = Quarantine(tmp_path).receive_bytes(pdf_with_embed)
    assert scan.status == "MALICIOUS"
    assert "embedded executable file" in scan.reason


def test_eicar_test_malware_signature_detected(tmp_path):
    """Industry-standard EICAR malware test string in an attachment is detected and blocked."""
    eicar = b"%PDF-1.7\nX5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*\n"
    scan = Quarantine(tmp_path).receive_bytes(eicar)
    assert scan.status == "MALICIOUS"
    assert "EICAR" in scan.reason


def test_email_with_malicious_bill_attachment_is_blocked_in_runtime():
    """An email with a malicious PDF bill (/Launch payload) is blocked by Airlock."""
    malicious_pdf = b"%PDF-1.7\n<< /S /Launch /F (calc.exe) >>"
    msg = {
        "id": "mal_bill",
        "from": "attacker@evil.example",
        "subject": "Overdue bill - urgent",
        "body": "Please see the attached bill.",
        "attachments": [{"name": "bill.pdf", "content": malicious_pdf}],
    }
    res = service.run_messages("alice", [msg])
    assert res["blocked"]
    reasons = " ".join(" ".join(r["reasons"]) for r in res["blocked"])
    assert "malicious" in reasons.lower() or "quarantined" in reasons.lower()
