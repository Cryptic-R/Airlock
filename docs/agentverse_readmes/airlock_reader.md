![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)

# Airlock Reader 📥

The input boundary of the Airlock system. It is the only component that touches raw untrusted
content: it returns the demo inbox, or normalises a pasted email into structured text, and hands
it to the orchestrator clearly marked as untrusted. It decides nothing.

**Agent-to-agent**: `ReadRequest(job_id, mode, raw_text)` → `ReadResult(job_id, ok, error, messages_json)` (protocol *AirlockReader 1.0.0*)

Keywords: email parsing, untrusted input, Airlock
