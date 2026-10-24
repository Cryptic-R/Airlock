![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)

# Airlock Bank 🏦

The settlement boundary of the Airlock system. It accepts only a typed, gate-approved action and
returns a receipt. It never sees the email, the planner's reasoning, or any free text — there is
no string parameter through which an instruction could arrive.

**Agent-to-agent**: `ExecRequest(job_id, action, receipt_hint, amount, payee_name)` → `ExecResult(job_id, ok, error, receipt)` (protocol *AirlockBank 1.0.0*)

Keywords: payment settlement, bank, Airlock
