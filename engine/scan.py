"""Hidden-content scanner.

The planner reads an email as text. A human reading the same email in a normal
mail client does *not* see the same thing: a mail client hides zero-width
characters, honours `display:none`, renders white-on-white as blank, and never
shows an HTML comment. That gap is a weapon. An attacker can address one set of
instructions to the human (innocuous) and a second, invisible set to the model
(pay the attacker), and a reviewer approving the card never sees why.

This module is the one place Airlock looks at the *bytes* of untrusted content
rather than its meaning. It returns a list of plain-English findings. It makes
no decision: a finding can only ever RAISE an action to human review (see the
GATE-HIDDEN layer in gate.py). It can never clear one. A clean scan is not
evidence that a message is safe -- it only means this particular trick wasn't
used -- so nothing downstream is allowed to treat "no findings" as approval.
"""
from __future__ import annotations

import re

# Zero-width / invisible formatting characters. None of these carry visible
# meaning in a mail client, so any run of them in a bill is a channel, not text.
_INVISIBLE = {
    "​": "zero-width space",
    "‌": "zero-width non-joiner",
    "‍": "zero-width joiner",
    "⁠": "word joiner",
    "﻿": "zero-width no-break space (BOM)",
    "­": "soft hyphen",
    "᠎": "Mongolian vowel separator",
}
# Bidirectional overrides can reorder text so the human reads one thing and the
# parser receives another (the classic "Trojan Source" trick).
_BIDI = {
    "‪", "‫", "‬", "‭", "‮",
    "⁦", "⁧", "⁨", "⁩",
}
# Private-use and tag characters (U+E0000 block) are a known steganographic
# channel for smuggling instructions past a human.
_TAG_RANGE = (0xE0000, 0xE007F)

_HTML_HIDDEN = re.compile(
    r"display\s*:\s*none"
    r"|visibility\s*:\s*hidden"
    r"|font-size\s*:\s*0"
    r"|color\s*:\s*#?(?:fff(?:fff)?|white)"
    r"|opacity\s*:\s*0",
    re.IGNORECASE,
)
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_BASE64_BLOB = re.compile(r"[A-Za-z0-9+/]{120,}={0,2}")
_DATA_URI = re.compile(r"data:[^\s,]{0,100},", re.IGNORECASE)
# Attachment/file references an agent might be tempted to "open" and act on.
_RISKY_FILE = re.compile(
    r"\b[\w\-./ ]{1,60}\.(?:exe|scr|js|vbs|ps1|bat|cmd|jar|hta|lnk|iso|html?|svg)\b",
    re.IGNORECASE,
)
# Dot-files / hidden config an attacker might plant to be auto-read ("crib files").
_HIDDEN_FILE = re.compile(
    r"(?:^|[\s/\\])\.(?:env|config|cfg|ini|htaccess|airlock|rules|mandates)\b"
    r"|\b(?:config|rules|mandates|override|allowlist)\.(?:json|ya?ml|txt)\b",
    re.IGNORECASE,
)


def scan_text(*parts: str) -> list[str]:
    """Return a list of hidden-content findings across the given text parts.

    Advisory only. The presence of any finding should raise the message to a
    human; the absence of findings proves nothing.
    """
    text = "\n".join(p for p in parts if p)
    findings: list[str] = []
    if not text:
        return findings

    seen_invis = sorted({_INVISIBLE[c] for c in text if c in _INVISIBLE})
    for name in seen_invis:
        findings.append(f"invisible character ({name}) hidden in the text")

    if any(c in _BIDI for c in text):
        findings.append("a right-to-left/bidi override that can reorder what you read")

    if any(_TAG_RANGE[0] <= ord(c) <= _TAG_RANGE[1] for c in text):
        findings.append("Unicode tag characters used to smuggle hidden instructions")

    if _HTML_HIDDEN.search(text):
        findings.append("text styled to be invisible (hidden/white/zero-size) in HTML")

    comments = _HTML_COMMENT.findall(text)
    if any(len(c) > 20 for c in comments):
        findings.append("instructions tucked inside an HTML comment")

    if _DATA_URI.search(text):
        findings.append("an inline data: URI that could carry a disguised payload")
    elif _BASE64_BLOB.search(text):
        findings.append("a long encoded (base64-like) blob that hides its contents")

    files = {m.group(0).strip() for m in _RISKY_FILE.finditer(text)}
    if files:
        shown = ", ".join(sorted(files)[:3])
        findings.append(f"a reference to a risky attachment/file ({shown})")

    if _HIDDEN_FILE.search(text):
        findings.append("a reference to a hidden config/rules file it wants read")

    return findings
